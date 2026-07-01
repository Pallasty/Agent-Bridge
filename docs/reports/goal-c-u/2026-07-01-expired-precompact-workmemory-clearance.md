# Expired Precompact Work Memory Clearance

Date: 2026-07-01

Status: `EXPIRED_PRECOMPACT_CLEARED / BACKED_UP / POSTCHECKED`

## Decision

Clear only expired `source:precompact` work-memory rows whose `ttl:14d` window
has already elapsed.

This is the second cleanup pass after the stale active session-lane clearance.
It does not touch the current shared active slot, the standing reversible
authorization policy row, IDE/create-file guardrail rows, durable memory,
forum thread status, runtime flags, daemons, DB schema, ranking behavior, or
repository code paths.

## Backup

Before clearing, a SQLite backup was created with Python's standard
`sqlite3.backup` API:

```text
source=/home/pallasting/.local/share/agent-bridge/state.db
backup=/home/pallasting/.local/share/agent-bridge/backups/state.before-expired-precompact-clearance.20260701T203000Z.db
size=192262144
sha256=8c3b28a9599c203f3eaa561711d6d7a2866bc6b2a02e7d9d54e39e2bda148cfc
```

## Clear Allowlist

All rows were project-scoped active `work_memory` rows with `source:precompact`
and `ttl:14d`.

| Key | Age at clearance | Result |
|---|---:|---|
| `work_memory_3d56857a5eed_019eaf44-973b-7c92-a4d8-f6fc05d8a09e_precompact` | 20.82 days | tombstoned |
| `work_memory_3d56857a5eed_e43c4cc0-0560-43d3-b881-3b2709b132b5_precompact` | 28.35 days | tombstoned |
| `work_memory_3d56857a5eed_019e818a-e429-75f3-b05f-45831fcc75ed_precompact` | 29.56 days | tombstoned |
| `work_memory_3d56857a5eed_d6103510-c1ff-447a-9f4f-9077183829af_precompact` | 30.65 days | tombstoned |
| `work_memory_3d56857a5eed_2a26ed1d-beff-4c8e-9f50-00a571ffc8dc_precompact` | 31.36 days | tombstoned |

MCP clear results:

```text
work_memory clear deleted=true for all 5 allowlisted keys
```

Post-clear store check:

```text
active_project_work_memory_count=7
all_5_allowlisted_rows_status=tombstoned
```

## Kept Active

These rows were intentionally not cleared:

- `work_memory_3d56857a5eed_shared_active` — current project lane;
- `work_memory_3d56857a5eed_codex-standing-reversible-authorization-20260701_active` — standing authorization policy;
- `work_memory_3d56857a5eed_codex-pallasting_active` — recent interactive PTY context, still within its 7-day TTL;
- `work_memory_18b072423e9a_shared_ide-extension-final-authority-2026-06-30` — IDE/create-file guardrail context;
- `work_memory_18b072423e9a_shared_ide-create-file-gate-runtime-2026-06-30` — IDE/create-file guardrail context;
- `work_memory_18b072423e9a_shared_ide-create-file-contract-2026-06-30` — IDE/create-file guardrail context;
- `work_memory_3d56857a5eed_shared_precompact` — recent shared precompact row, still inside its TTL.

## Rollback Boundary

The cleanup is reversible enough under the standing authorization policy:

- a full SQLite backup exists before the clear;
- the rows are scratchpad-style precompact state, not durable project memory;
- the tombstoned rows retain their content in the store;
- restoring any row would be a `work_memory save` or SQLite restore from the
  backup if a later session proves the content is still needed.

## Boundary

This cleanup did not:

- delete durable memory rows;
- close or edit forum threads;
- change runtime env flags;
- restart daemons;
- modify DB schema;
- modify retrieval ranking;
- change repository code.
