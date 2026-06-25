# GTE 768 Mac Stale Reader Cleanup

Date: 2026-06-25

Status: `MAC_STALE_READERS_CLEARED / GTE_SQL_STILL_PASS / AIO2_NOT_MIGRATED`.

Scope: Mac-side stale MCP reader cleanup and read-only verification after the
user completed Mac full GTE 768 migration. This report records the controlled
cleanup of stale MCP reader processes only. It does not authorize aio2 live DB
mutation, runtime env changes, or production `memory_search` changes.

## Before Cleanup

Mac `doctor --json` reported:

```text
ok=true
fails=0
warns=3
mcp_servers=12 total: 2 current .real, 10 stale .real
```

Stale MCP PIDs holding the Mac live DB/WAL open:

```text
14809
14905
31138
31748
37645
43383
44667
59383
61317
70041
```

## Cleanup Action

Sent `TERM` only to the stale MCP PIDs above.

Not touched:

- `agent-bridge.real daemon-http`;
- `agent-bridge.real daemon`;
- `agent-bridge.real palace`;
- current `.real` MCP readers.

All stale PIDs exited after `TERM`; no `KILL` was needed.

## Post-Cleanup Doctor

Mac `doctor --json` after cleanup:

```text
ok=true
fails=0
warns=2
mcp_servers=3 MCP server(s) - all executing current agent-bridge.real
```

Remaining warnings:

- `/Users/pallasting/.local/bin/ab-system-control` missing;
- desktop runtime cannot read desktop status without `ab-system-control`.

These are Mac desktop-helper warnings, not GTE vector/readiness blockers.

## Post-Cleanup SQL Invariants

Direct SQL still verifies the Mac live DB as fully GTE 768:

```text
db=/Users/pallasting/Library/Application Support/agent-bridge/state.db
active_total=3248
embedded=3248
null_or_empty=0
gte_good=3248
gte_bad_dim=0
old_or_non_gte_active_embedded=0
bucket backend=gte-multilingual-base bytes=3072 dim=768 rows=3248
```

## Post-Cleanup DB Handles

After cleanup, DB handles were held by expected current runtime surfaces:

```text
agent-bridge.real daemon-http
agent-bridge.real daemon
agent-bridge.real palace
current agent-bridge.real mcp readers
```

No stale MCP PIDs remained.

## Remaining Follow-Up

Mac `continuity-report --json` still reports:

```text
active_total=3248
embedded=0
stale_vectors=0
stale_frac=0.000
backends=[]
```

This contradicts direct SQL and should be treated as a continuity-report bug or
report-path mismatch. It is not evidence that the Mac DB lacks embeddings.

## Decision

Mac stale-reader blocker is cleared.

Mac GTE state now stands at:

```text
mac_gte_migrated=true
mac_stale_mcp_readers=false
mac_gte_sql_pass=true
mac_doctor_fails=0
mac_doctor_warns=2
mac_continuity_report_discrepancy=true
```

Overall dual-node live cut-over remains `NO_GO` because aio2 is not migrated.
