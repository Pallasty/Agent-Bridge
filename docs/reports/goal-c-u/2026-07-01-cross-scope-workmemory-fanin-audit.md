# Cross-Scope Work Memory Fan-In Audit

Date: 2026-07-01

Status: `READ_ONLY_AUDIT / NO_CLEAR / CROSS_SCOPE_ALLOWLIST_PROPOSED`

## Decision

Do not clear any additional `work_memory` rows in this slice.

After the exact Agent-Bridge stale-active and expired-precompact cleanup
passes, `work_memory list` for `/Data/CascadeProjects/agent-bridge` still
surfaces parent-scope and legacy-path rows through cross-scope fan-in. This
report separates current Agent-Bridge continuity from broader
`CascadeProjects`, legacy `/Programs/...`, and other project scopes so future
sessions do not mistake stale scratchpads for current Agent-Bridge tasks.

## Scope

Store:

```text
/home/pallasting/.local/share/agent-bridge/state.db
```

Current repo scope:

```text
project:/Data/CascadeProjects/agent-bridge
```

Query posture:

- Python standard-library SQLite opened the store with `mode=ro`;
- only `kind='work_memory'` and `status='active'` rows were inspected;
- TTL expiry was inferred from `ttl:Nd` tags and `updated_at`;
- no `work_memory clear`, durable memory deletion, forum status change, or
  runtime operation was performed.

## Current Exact Project Scope

The exact current Agent-Bridge project scope has 7 active `work_memory` rows,
all still inside their TTL windows.

| Class | Count | Read |
|---|---:|---|
| current shared lane | 1 | priority cleanup sequence complete; awaiting fresh lane |
| standing authorization policy | 1 | keep active |
| recent interactive PTY context | 1 | within `ttl:7d` |
| IDE/create-file guardrail context | 3 | within `ttl:45d` |
| recent shared precompact | 1 | within `ttl:14d` |

This matches the post-check from:

```text
docs/reports/goal-c-u/2026-07-01-expired-precompact-workmemory-clearance.md
```

No exact-scope Agent-Bridge row is currently a TTL-expired cleanup candidate.

## Fan-In Findings

Active `work_memory` rows by scope:

| Scope | Active | TTL-expired | Notes |
|---|---:|---:|---|
| `project:/Data/CascadeProjects/agent-bridge` | 7 | 0 | current exact repo scope |
| `project:/Data/CascadeProjects` | 6 | 4 | parent-scope fan-in; contains stale precompact rows and two fresh rows |
| `project:/Programs/Users/Pallasting/Documents/CascadeProjects/agent-bridge` | 9 | 1 | legacy path; mostly recent 2026-06-29/30 completed slice notes |
| `project:/Programs/Users/Pallasting/Documents/CascadeProjects` | 4 | 2 | legacy parent path; portfolio notes plus expired precompact rows |
| other project scopes under `/Data/CascadeProjects` | 18 | 18 | cross-project expired rows; not Agent-Bridge-local cleanup in this slice |
| old `/Users/pallasting/Projects/...` scopes | 2 | 2 | old machine/path handoff rows |

The important Agent-Bridge-adjacent fan-in candidates are not exact-scope rows.
They should therefore be handled only by a separate cross-scope cleanup packet
with its own backup and allowlist.

## Proposed Cross-Scope Allowlist

These rows are narrow candidates for a future cleanup pass because they are
TTL-expired scratchpads and belong to parent or legacy Agent-Bridge-adjacent
scopes:

| Key | Scope | Age | Reason |
|---|---|---:|---|
| `work_memory_632a30f8be46_019eae07-16b3-76c3-a66f-50bd12bbed85_precompact` | `project:/Data/CascadeProjects` | 17.29d | expired `source:precompact`, `ttl:14d` |
| `work_memory_632a30f8be46_019eb572-f409-7023-adb9-3d21b3ae3905_precompact` | `project:/Data/CascadeProjects` | 18.08d | expired `source:precompact`, `ttl:14d` |
| `work_memory_632a30f8be46_d1154ffd-3f62-44c1-bdea-e6993aacf6cc_precompact` | `project:/Data/CascadeProjects` | 27.49d | expired `source:precompact`, `ttl:14d` |
| `work_memory_632a30f8be46_78d33189-0149-4b0f-962c-48b38eca980f_precompact` | `project:/Data/CascadeProjects` | 30.66d | expired `source:precompact`, `ttl:14d` |
| `work_memory_18b072423e9a_019eae07-16b3-76c3-a66f-50bd12bbed85_precompact` | `project:/Programs/Users/Pallasting/Documents/CascadeProjects` | 20.86d | expired legacy-path precompact |
| `work_memory_18b072423e9a_019ead84-8774-7863-9f68-f40c4ed79193_precompact` | `project:/Programs/Users/Pallasting/Documents/CascadeProjects` | 22.01d | expired legacy-path precompact |
| `work_memory_93a0f4b43b9e_019eaf44-973b-7c92-a4d8-f6fc05d8a09e_precompact` | `project:/Programs/Users/Pallasting/Documents/CascadeProjects/agent-bridge` | 20.87d | expired legacy Agent-Bridge precompact |

Do not include non-expired parent/legacy rows in that cleanup. In particular,
preserve these until their TTLs expire or a separate closeout proves they are
superseded:

| Key | Reason to preserve for now |
|---|---|
| `work_memory_632a30f8be46_shared_active` | fresh parent-scope semantic-rebalance cleanup note, age 0.04d |
| `work_memory_632a30f8be46_shared_precompact` | fresh parent-scope bounded-latch precompact, age 2.69d, still inside TTL |
| `work_memory_18b072423e9a_shared_project-portfolio-2026-06-29` | fresh legacy parent portfolio note, age 1.96d |
| `work_memory_18b072423e9a_shared_shared_project-portfolio-2026-06-29` | fresh legacy parent portfolio note, age 1.98d |
| recent legacy Agent-Bridge rows from 2026-06-29/30 | inside TTL; useful as migration/old-path context |

## Cross-Project No-Go

This audit observed many expired rows under other project scopes such as
`AiOT`, `onsen-hd`, `biocortex-rs`, and old worktrees. They are real hygiene
pressure, but they are not Agent-Bridge-local. A future broad cleanup should be
posted as a CascadeProjects-wide maintenance packet, not mixed into an
Agent-Bridge report.

## Recommended Next Step

If continuing queue hygiene:

1. Create a SQLite backup of `state.db`.
2. Clear only the 7 proposed cross-scope allowlist keys above.
3. Post-check that each key is tombstoned or no longer returned by
   `work_memory get`.
4. Verify exact `project:/Data/CascadeProjects/agent-bridge` still has the same
   7 active rows.
5. Post to thread `#102` with the backup hash and boundary.

If deferring cleanup:

- treat this report as the current state packet;
- continue with another read-only lane such as workflow-feedback held-out
  evidence, board-status staleness review, or a broad CascadeProjects cleanup
  proposal.

## Boundary

This report did not:

- clear any `work_memory` row;
- delete durable memory;
- close or edit forum threads;
- change runtime env flags;
- restart daemons;
- modify DB schema;
- modify retrieval ranking or tool routing;
- change repository code paths.
