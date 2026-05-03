# Memory Snapshots

Cross-session agent memory exported from the agent-bridge SQLite store.

## Format

Each file is **JSONL** (one `MemoryRecord` per line), compatible with
`memory_import` via the MCP tool or the `agent-cli memory import` command.

## Files

| File | Date | Records | Notes |
|---|---|---|---|
| `memory_20260501.jsonl` | 2026-05-01 | 233 | Initial sync — AiOT + agent-bridge sessions |
| `inject/ab_ai_kernel_v1.jsonl` | 2026-05-02 | 14 | AI-first kernel: layered architecture, Hub, memory/search/graph, lifecycle, checklist (`tags`: `ab-inject`) |
| `inject/ab_ai_bridge_feedback_v1.jsonl` | 2026-05-02 | 9 | Agent-UX / ops feedback + phased roadmap + Phase B/C shipped anchor (`tags`: `ab-feedback`) |

## AI-oriented injection bundle (`inject/`)

`inject/ab_ai_kernel_v1.jsonl` is formatted for **model consumption**: each line is
one small `MemoryRecord` with dense English **KEYWORDS** (better for the built-in
feature-hash embedding), plus short **ZH** lines and machine-oriented **SIGNAL**
headers. After import, recall with:

- `memory_search(query="agent-bridge hub semantic", mode="semantic", threshold=0.3)`
- or `memory_search(..., mode="hybrid", tags_any=["ab-inject"])`

Import (merge without clobbering unrelated keys — use `skip` or `newer_wins`):

```text
memory_import(path="memory_snapshots/inject/ab_ai_kernel_v1.jsonl", conflict_policy="skip")
```

Optional second bundle (observability / graph export / security roadmap cards):

```text
memory_import(path="memory_snapshots/inject/ab_ai_bridge_feedback_v1.jsonl", conflict_policy="skip")
```

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

By default, `memory_export` writes `MemoryRecord` JSONL only. For a **portable
graph slice**, pass **`edges_out_path`** (MCP): the store also writes a second
JSONL file, one `MemoryEdgeExport` per line, for every edge whose **both**
endpoints appear among the exported memory keys. Restore with **`memory_import`**
using the same **`path`** plus optional **`edges_path`** pointing at that
companion file. Edges that touch memories outside the export set are omitted
by design.
