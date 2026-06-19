# Memory Continuity T4 Consolidation Queue

Date: 2026-06-19

T4 adds a read-only queue for memory consolidation candidates. It turns T1/T2
continuity metadata and T3 retrieval feedback into review buckets, but it does
not mutate memory state.

## Interface

New MCP tool:

- `memory_consolidation_queue`

Inputs:

- `scope`: optional memory scope filter.
- `scope_mode`: `local_only`, `local_plus_global`, or `exploratory`.
- `skip_tags`: default `auto_curated`, `alert`, `ttl:7d`.
- `skip_kinds`: default `skill`, `work_memory`, `snapshot`.
- `max_records`: maximum records scanned.
- `max_per_bucket`: maximum rows returned per bucket.
- `preview_chars`: content preview length.
- `large_content_chars`: threshold for high-token candidates.
- `low_use_max_access_count`: access-count ceiling for low-use candidates.

## Buckets

The report returns schema `agent_bridge.memory_consolidation_queue.v0` with these
candidate buckets:

- `handoff_to_decision`: active `session_handoff` rows that should be reviewed
  for durable decision or lesson extraction.
- `duplicate_lessons`: targets of `retrieval_feedback:duplicate` feedback rows.
- `stale_warnings`: rows tagged `continuity_confidence:stale`, plus targets of
  stale retrieval feedback.
- `harmful_memories`: targets of harmful retrieval feedback.
- `too_large_memories`: targets of too-large retrieval feedback.
- `high_token_low_use`: large rows with low observed access count.
- `intentional_orphans`: edge-free archive or intentional orphan rows.

Each row includes key, kind, reason, score, importance, access count, updated time,
content size, preview, tags, and related keys.

## Boundary

This tool is read-only. It does not:

- archive or supersede memory rows
- create graph edges
- merge duplicate rows
- alter `memory_search` ranking
- alter `session_bootstrap` selection
- invoke BioCortex or neural critics

The queue is meant to feed human review, deterministic consolidation tools, and
future offline critic evaluation.

## Verification

Focused tests cover:

- Feedback, stale metadata, high-token low-use rows, handoffs, and intentional
  orphans are assigned to the expected buckets.
- The MCP tool returns buckets from the store without deleting or mutating the
  source memory.
- Codex-essential policy exposes `memory_consolidation_queue`.

Commands:

```bash
cargo test -p ab-bridge memory_consolidation_queue -- --nocapture
cargo test -p ab-bridge tool_policy_codex_essential_ -- --nocapture
```

## Next Step

T5 should run BioCortex shadow trials over baseline candidates, graph-neighborhood
slices, and T3/T4 feedback buckets. It should compare alternate ordering and
suppression sets without changing default AB memory authority.
