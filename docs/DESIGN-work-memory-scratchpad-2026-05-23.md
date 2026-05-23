# Work Memory Scratchpad

Date: 2026-05-23
Status: implemented as v0 MVP

## Problem

Codex desktop can compact a session before the agent has naturally reached a
clean handoff point. Durable memories (`lesson`, `decision`, `todo`,
`session_handoff`) are too semantic for this job: they should preserve learned
facts, not raw in-flight state. The missing surface is a short-lived project or
session scratchpad that can survive context compaction without polluting
long-term recall.

## Feasibility Check

The current Agent-Bridge architecture already has the three required pieces:

- Storage: `MemoryRecord` can hold a new `kind = "work_memory"` row with
  `scope = "project:/abs/path"`. No SQLite migration is required for the MVP.
- Recovery: `session_bootstrap` already injects scoped memory blocks with
  independent token budgets, so work memory can surface early in a new context.
- Capture: `session_lifecycle_step(precompact)` is already called by the
  precompact hook. It can save a capped scratch snapshot before curation and
  finalization.

This makes a v0 implementation low risk: one MCP tool plus two lifecycle
integration points.

## v0 Design

The MVP adds a single MCP tool:

```text
work_memory(op = save | list | get | clear)
```

Rows are stored as normal memories with:

- `kind = "work_memory"`
- `scope = "project:<cwd>"`
- deterministic keys:
  `work_memory_<cwd_hash>_<session-or-shared>_<slot>`
- tags such as `work_memory`, `slot:active`, `session:<id>`, `ttl:14d`

`save` overwrites the same slot by default. This is deliberate: active work
state should be fresh, small, and replaceable. Durable conclusions still go to
`memory_save`.

`session_bootstrap` now includes an `Active Work Memory` block capped by its own
budget, before the broader project-state digest and main memory rows.

`session_lifecycle_step(precompact)` saves a capped `precompact` slot by
default unless `dry_run=true` or `save_work_memory=false`. The snapshot stores
the tail of `conversation_text`, limited to 6000 characters, so a post-compact
agent can reconstruct what was in flight without needing the full transcript in
model context.

## Boundaries

Work memory is not a replacement for durable memory.

- Use `work_memory` for active file lists, current hypothesis, running task
  state, test evidence, and next step.
- Use `memory_save` for decisions, lessons, recurring user preferences, project
  facts, and handoffs that should remain important after the task is complete.

The MVP intentionally reuses the memory table. A future version may add a
dedicated table if we need TTL enforcement, per-session garbage collection, or
non-synced local-only scratch records.

## Follow-Up

- Add a lifecycle cleanup pass that archives expired `work_memory` rows by
  reading `ttl:Nd` tags.
- Add a compact projection for `work_memory list` that is even shorter for
  Codex lean profiles.
- Consider a local-only storage backend if raw precompact excerpts should never
  enter cross-device memory sync.
