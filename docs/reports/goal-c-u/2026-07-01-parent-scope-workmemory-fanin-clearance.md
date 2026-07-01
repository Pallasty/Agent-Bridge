# Parent Scope Work Memory Fan-In Clearance

Date: 2026-07-01

Status: `PARENT_SCOPE_FANIN_CLEARED / BACKED_UP / POSTCHECKED`

## Decision

Clear stale `work_memory` rows from the parent workspace scope
`project:/Data/CascadeProjects` that were still fanning into the Agent-Bridge
project view.

This is the third queue-hygiene cleanup pass after:

- stale completed session-lane active cleanup;
- expired Agent-Bridge precompact cleanup.

The cleanup keeps the current Agent-Bridge project rows that still carry useful
planning or guardrail context. It does not touch durable memory, forum thread
status, runtime flags, daemons, DB schema, retrieval ranking, or repository code
paths.

## Backup

Before clearing, a SQLite backup was created with Python's standard
`sqlite3.backup` API because the `sqlite3` shell was not installed:

```text
source=/home/pallasting/.local/share/agent-bridge/state.db
backup=/home/pallasting/.local/share/agent-bridge/backups/state.before-parent-scope-workmemory-fanin-clearance.20260701T194414Z.db
size=192262144
sha256=671b5dadb7ad2f5ed2bbf07b0e3b7110aef4848354c4682648d6058012a746fe
```

## Clear Allowlist

These rows were cleared from `project:/Data/CascadeProjects`:

| Key | Class | Reason |
|---|---|---|
| `work_memory_632a30f8be46_019eae07-16b3-76c3-a66f-50bd12bbed85_precompact` | expired precompact | 2026-06-13 BioCortex Slice 38 context; `ttl:14d` elapsed; not current Agent-Bridge work |
| `work_memory_632a30f8be46_019eb572-f409-7023-adb9-3d21b3ae3905_precompact` | expired precompact | 2026-06-14 instinct review-status/receipt development context; `ttl:14d` elapsed |
| `work_memory_632a30f8be46_78d33189-0149-4b0f-962c-48b38eca980f_precompact` | expired precompact | 2026-06-01 onsen context-compaction handoff; `ttl:14d` elapsed and outside current project |
| `work_memory_632a30f8be46_d1154ffd-3f62-44c1-bdea-e6993aacf6cc_precompact` | expired precompact | 2026-06-04 voice/Piper context-compaction handoff; `ttl:14d` elapsed and low-importance scratchpad |
| `work_memory_632a30f8be46_shared_precompact` | stale shared precompact | bounded-latch owner-gated v38 design text superseded by later v38 implementation, verification, and stale-gate cleanup evidence |
| `work_memory_632a30f8be46_shared_active` | completed shared active | semantic rebalance PR #32 merge/cleanup row marked `completed`; no longer an open lane |

## Post-Clear Verification

Each cleared key was checked with `work_memory get` after the clear. All six
returned:

```text
work memory key not found
```

The Agent-Bridge project-scoped `work_memory list` now returns only seven
project rows and no parent-scope fan-in rows.

## Kept Active

These rows remain visible for `/Data/CascadeProjects/agent-bridge`:

| Key | Reason |
|---|---|
| `work_memory_3d56857a5eed_shared_active` | current project continuity slot |
| `work_memory_3d56857a5eed_shared_precompact` | recent project precompact row; still inside TTL |
| `work_memory_3d56857a5eed_codex-standing-reversible-authorization-20260701_active` | standing reversible-operations authorization policy |
| `work_memory_3d56857a5eed_codex-pallasting_active` | recent interactive PTY context; still inside 7-day TTL |
| `work_memory_18b072423e9a_shared_ide-create-file-contract-2026-06-30` | IDE/create-file guardrail context; still inside 45-day TTL |
| `work_memory_18b072423e9a_shared_ide-create-file-gate-runtime-2026-06-30` | IDE/create-file guardrail context; still inside 45-day TTL |
| `work_memory_18b072423e9a_shared_ide-extension-final-authority-2026-06-30` | IDE/create-file final-authority context; still inside 45-day TTL |

## Rollback Boundary

This cleanup is reversible enough under the standing authorization policy:

- a full SQLite backup exists before the clear;
- the rows are scratchpad-style `work_memory`, not durable project memory;
- the cleared rows were already expired, completed, or superseded;
- restoring any row would be a `work_memory save` or SQLite restore from the
  backup if a later session proves the content is still needed.

## Boundary

This cleanup did not:

- delete durable memory rows;
- close or edit forum threads;
- change runtime environment flags;
- restart daemons;
- modify DB schema;
- modify retrieval ranking;
- change repository code paths.
