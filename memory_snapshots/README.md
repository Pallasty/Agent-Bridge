# Memory Snapshots

Cross-session agent memory exported from the agent-bridge SQLite store.

## Format

Each file is **JSONL** (one `MemoryRecord` per line), compatible with
`memory_import` via the MCP tool or the `agent-cli memory import` command.

## Files

| File | Date | Records | Notes |
|---|---|---|---|
| `memory_20260501.jsonl` | 2026-05-01 | 233 | Initial sync — AiOT + agent-bridge sessions |

## How to restore

```bash
# Via MCP tool (in Auggie / Claude Code session)
memory_import(path="memory_snapshots/memory_20260501.jsonl", conflict_policy="newer_wins")

# Via agent-cli
agent-cli memory import memory_snapshots/memory_20260501.jsonl --policy newer_wins
```

## How to update

```bash
# Export latest snapshot (via MCP)
memory_export(path="memory_snapshots/memory_YYYYMMDD.jsonl")

# Then commit
git add memory_snapshots/ && git commit -m "chore(memory): sync snapshot YYYYMMDD"
git push
```

## Note on graph edges

`memory_export` serialises `MemoryRecord` rows only — graph edges
(`memory_edges` table) are **not** included. Re-link with `memory_link`
after import if edge topology matters.
