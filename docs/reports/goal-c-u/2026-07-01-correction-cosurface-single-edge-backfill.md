# Correction Co-Surface Single-Edge Backfill

Date: 2026-07-01

Status: `BACKFILL_EXECUTED / READ_ONLY_VERIFIED / COSURFACE_DISABLED`

## Decision

After owner approval in the active Codex session, execute only the single
correction-edge backfill identified by the preflight packet.

Do not enable `AGENT_BRIDGE_CORRECTION_COSURFACE`, do not restart daemons, do
not deploy, and do not combine this maintenance write with any retrieval-policy
or ranking-policy change.

## Input Packet

Preflight report:

- `docs/reports/goal-c-u/2026-07-01-correction-cosurface-live-backfill-preflight.md`

The preflight found exactly one active correction row with a valid active target
and no `corrects` edge:

```text
correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682
  --corrects-->
session_handoff_present_voice_tts_subsystem_20260601
```

The owner then approved proceeding with the agent's recommended next step. This
report treats that approval as limited to the one-row backfill only.

## Backup

Before writing, a SQLite backup was created through Python's standard
`sqlite3` backup API.

Source:

```text
/home/pallasting/.local/share/agent-bridge/state.db
```

Backup:

```text
/home/pallasting/.local/share/agent-bridge/backups/state.before-correction-edge-backfill.20260701T114243.db
```

Backup size:

```text
192262144 bytes
```

Backup SHA-256:

```text
9da1a973af97d89d86d90ffa8e8bbb115fa9d6c5bbdb14303b73604892789174
```

## Write Performed

The write was executed as one SQLite transaction against the live store.

Edge inserted:

| from_key | to_key | edge_type | weight | created_at |
|---|---|---|---:|---:|
| `correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682` | `session_handoff_present_voice_tts_subsystem_20260601` | `corrects` | 1.4 | 1782931382 |

Write shape:

```sql
INSERT INTO memory_edges (from_key, to_key, edge_type, weight, created_at)
VALUES (?, ?, 'corrects', 1.4, ?)
ON CONFLICT(from_key, to_key, edge_type)
DO UPDATE SET weight = excluded.weight;
```

Preconditions checked immediately before the write:

- correction row exists;
- correction row is active;
- correction row kind is `feedback`;
- target row exists;
- candidate `corrects` edge did not already exist.

## Before And After

| Metric | Before | After |
|---|---:|---:|
| active memories | 666 | 666 |
| active feedback corrections | 5 | 5 |
| `corrects` edges | 4 | 5 |
| candidate edge exists | 0 | 1 |

No memory rows were inserted, updated, archived, superseded, or tombstoned by
this maintenance step. Only the named `memory_edges` row changed.

## Read-Only Verification

Post-write verification used a read-only SQLite connection:

```text
file:/home/pallasting/.local/share/agent-bridge/state.db?mode=ro
```

Result:

```json
{
  "active_memories": 666,
  "active_corrections": 5,
  "corrects_edges": 5,
  "missing_valid_correction_edges": [],
  "candidate_edge": {
    "from_key": "correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682",
    "to_key": "session_handoff_present_voice_tts_subsystem_20260601",
    "edge_type": "corrects",
    "weight": 1.4,
    "created_at": 1782931382
  }
}
```

The verification intentionally used normal read-only mode rather than
`immutable=1` because the live store had active WAL/SHM sidecar files during
the maintenance window.

## Runtime Boundary

The following were verified after the write:

- repository working tree was clean before this report was added;
- concurrent docs-only queue-audit commits were present locally through
  `b1c0666` before this report was added;
- all visible `agent-bridge.real` processes lacked
  `AGENT_BRIDGE_CORRECTION_COSURFACE`;
- MCP lifecycle remained `ready`;
- readiness warnings remained `0`;
- failing tool count remained `0`.

This backfill does not enable correction co-surface read behavior. It only makes
the existing live graph consistent with the already-landed A1 write-path rule.

## Remaining Gate

`AGENT_BRIDGE_CORRECTION_COSURFACE=1` remains a separate owner decision.

Recommended shape if that gate opens:

1. Start a short A/B or shadow window with the env flag enabled.
2. Inspect before/after top-k diffs for queries that hit corrected originals.
3. Confirm `exclude_kinds` behavior remains intact in live use.
4. Decide whether to keep the flag enabled.

Do not treat this single-edge backfill as authorization for default retrieval
policy changes.
