# Memory Continuity T3 Retrieval Feedback

Date: 2026-06-19

T3 adds a low-friction feedback surface for retrieved memories. The goal is to
record whether a retrieved or bootstrapped memory row was useful, stale, harmful,
missing, or too large without changing retrieval ranking yet.

## Interface

New MCP tool:

- `memory_retrieval_feedback`

Inputs:

- `memory_key`: retrieved memory being judged. Required unless `outcome=missing`.
- `outcome`: `used`, `ignored`, `stale`, `duplicate`, `harmful`, `missing`, `too_large`.
- `source`: `memory_search`, `memory_get`, `session_bootstrap`, or `manual`.
- `query`: optional retrieval query or active task context.
- `note`: optional compact reason for the label.
- `retrieved_keys`: optional keys from the same retrieval event.
- `related_keys`: optional extra context keys.
- `importance`: optional override; otherwise defaults by outcome.

`too-large` is accepted as an input alias and normalized to `too_large`.

## Storage

The tool writes a `kind=feedback` memory with stable tags:

- `retrieval_feedback`
- `retrieval_feedback:<outcome>`
- `retrieval_source:<source>`
- `target:<sanitized-memory-key>` when a target exists

The feedback memory's `related_keys` includes the target, retrieved keys, and
explicit related keys after de-duplication.

When `memory_key` exists and the outcome is not `missing`, the tool creates an
outcome-specific edge from feedback to target:

- `retrieval_used`
- `retrieval_ignored`
- `retrieval_stale`
- `retrieval_duplicate`
- `retrieval_harmful`
- `retrieval_too_large`

`missing` can be recorded without a target and intentionally creates no edge.
Existing related keys can be linked with `retrieval_context`.

## Boundary

This is telemetry only. It does not change:

- `memory_search` ranking
- `session_bootstrap` selection
- continuity-kernel ordering
- BioCortex side-signal behavior

That boundary keeps T3 safe to deploy before ranking math is calibrated. The
feedback data becomes evidence for T4 consolidation and later ranking experiments.

## Verification

Focused tests cover:

- Targeted stale feedback saves a feedback memory and creates a `retrieval_stale`
  edge to the target.
- `missing` feedback works without a target and returns no edge.
- Non-missing feedback rejects missing target memories.
- Codex-essential policy exposes `memory_retrieval_feedback`.

Commands:

```bash
cargo test -p ab-bridge memory_retrieval_feedback -- --nocapture
cargo test -p ab-bridge tool_policy_codex_essential_ -- --nocapture
```

## Next Step

T4 should consume these feedback rows conservatively: first as consolidation
candidates for stale, duplicate, harmful, and too_large memories; only later as a
bounded ranking signal after query-level false-positive checks.
