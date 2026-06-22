# Goal C U Follow-Up - Aio2 Null FTS Hygiene

Date: 2026-06-21

Host: Linux/Aio2

Scope: live DB hygiene and stale MCP writer cleanup after
`docs/reports/goal-c-u/2026-06-21-aio2.md`.

This follow-up records a reversible operational hygiene pass. It did not change
Rust code, add an MCP surface, alter retrieval ranking, approve candidate
expansion, authorize an executor, or execute a manual DB backfill update.

## Problem

The Aio2 `U` report found fresh active memories with `fts_content IS NULL`.
During the hygiene pass, new S123 rows appeared with the same issue, increasing
the live null count from 2 to 5.

Pre-fix null rows:

| key | kind | trigger tag |
|---|---|---|
| `biocortex_s122_shadow_plan_20260621` | `session_handoff` | yes |
| `biocortex_rs_s122_readiness_guarded_shadow_plan_20260621` | `decision` | yes |
| `biocortex_s123_heldout_falsifier_20260621` | `session_handoff` | yes |
| `biocortex_rs_s123_readiness_guarded_heldout_falsifier_20260621` | `decision` | yes |
| `work_memory_28601f2a7ebe_shared_active` | `work_memory` | no |

For rows with a `continuity_retrieval_trigger:*` tag, null `fts_content` means
the durable memory body is still in `memories_fts`, but the dedicated continuity
retrieval trigger is not projected into FTS. That weakens proactive handoff
recall for the exact continuation phrases the memory author supplied.

## Backup

Before any possible mutation, a SQLite `.backup` was taken from the live DB.
The backup was then checked with `PRAGMA integrity_check`, which returned `ok`.

Backup created with SQLite `.backup`:

```text
/home/pallasting/.local/share/agent-bridge/backups/state-pre-null-fts-hygiene-20260621T170540Z.db
```

The backup file was present and approximately `1.2G`.
The backup contained `6177` memory rows and `5` rows with null `fts_content`.

## Fix

No manual SQL backfill was executed.

After the backup and before an `UPDATE` was issued, the live DB was observed at
`memories.fts_content IS NULL = 0`. The current `.real` MCP clients had
refreshed onto the v36 writer path, and the affected rows now carried the
current projection contract from `crates/store/src/sqlite.rs`:

- if continuity retrieval triggers exist, set:
  `content || "\n\nretrieval trigger:\n" || trigger_lines || "\n"`;
- otherwise set `fts_content = content`.

SQLite update triggers keep the stored `memories_fts` row aligned through
`COALESCE(new.fts_content, new.content)`.

Rows manually backfilled: `0`.
Rows observed self-healed before mutation: `5`.

## Verification

Post-fix checks:

| check | result |
|---|---|
| `SELECT COUNT(*) FROM memories WHERE fts_content IS NULL` | `0` |
| `SELECT COUNT(*) FROM memories WHERE status='active' AND fts_content IS NULL` | `0` |
| backup `PRAGMA integrity_check` | `ok` |
| live `PRAGMA quick_check` | `ok` |
| FTS query `continuing AND S123 AND replay` | hit all four S122/S123 BioCortex rows |
| FTS query `Goal AND C AND alignment` | hit the Agent-Bridge alignment S123 row |

The four continuity rows now have non-null FTS projections with a
`retrieval trigger:` suffix. The `work_memory` row has `fts_content` equal to
its content because it has no continuity retrieval trigger.

## Stale MCP Writer Cleanup

Before cleanup, `agent-bridge.real doctor --json` initially showed:

- 2 current `.real` MCP servers;
- 8 stale `.real (deleted)` MCP servers;
- 0 direct `agent-bridge` binary servers;
- 0 unknown servers.

A later `/proc` snapshot showed 3 current `.real` MCP servers and 7 stale
`.real (deleted)` MCP servers. A SIGTERM script was prepared to target only
stale MCP child processes, but by the time it ran it matched zero stale PIDs.
No parent Codex, Claude, or Cursor processes were killed.

After a short delay, `agent-bridge.real doctor --json` showed:

- `ok=true`;
- `fails=0`;
- `warns=2`;
- `mcp_servers`: `ok`, with 4 MCP servers all executing current
  `agent-bridge.real`;
- remaining warnings were only the missing `ab-system-control` desktop helper
  checks.

## Boundaries

This fix did not:

- change `memories.content`;
- change memory ranking logic;
- change production search order;
- add or remove tools;
- write BioCortex approvals;
- approve runtime candidate-set expansion;
- restart parent editor or agent clients.

## Next Watch

The next few memory writes should be watched for recurrence:

```sql
SELECT key, kind, created_at, updated_at
FROM memories
WHERE fts_content IS NULL
ORDER BY updated_at DESC;
```

If null rows reappear, the remaining source is likely a still-running client
that respawned an older binary or a non-MCP writer path that bypasses current
`memory_save`.
