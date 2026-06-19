# Memory Continuity T5 BioCortex Shadow Trial

Date: 2026-06-19

T5 adds a read-only BioCortex shadow-trial packet for AB memory continuity. It is
designed to compare baseline `memory_search` candidates with graph-neighborhood
and T3/T4 feedback controls without changing the default retrieval path.

## Board Context

The BioCortex board thread currently treats substrate-discovered selection as the
open frontier. The stale S93/S94/S95 sequence is not the current ground truth, and
AB should not claim that BioCortex has already discovered a production retrieval
selection mechanism.

For T5, BioCortex-rs is therefore treated as an Agent Cognitive Substrate
Extension candidate, not as retrieval authority.

## Interface

New MCP tool:

- `memory_biocortex_shadow_trial`

Inputs:

- `query`: required baseline `memory_search` query.
- `tags_any`: optional tag filter forwarded to baseline search.
- `limit`: baseline candidate limit.
- `scope`: optional memory scope used for the embedded T4 queue slice.
- `scope_mode`: `local_only`, `local_plus_global`, or `exploratory`.
- `neighbor_limit`: maximum graph-neighbor rows collected per baseline candidate.
- `queue_max_records`: maximum rows scanned for the T4 queue.
- `queue_max_per_bucket`: maximum rows considered per T4 bucket.

## Output

The report returns schema `agent_bridge.memory_biocortex_shadow_trial.v0` and
includes only hashes, counts, and redacted rows:

- `baseline`: hash-only order summary from the current `memory_search` result.
- `graph_neighborhood`: hash-only neighbor rows around baseline candidates.
- `consolidation_queue`: T4 bucket counts, not raw queue rows.
- `suppression_set`: hash-only rows from T3/T4 duplicate, stale, harmful, and
  too-large feedback buckets.
- `advisory_control_order`: deterministic suppressed-to-tail control order, never
  used as the actual return order.
- `current_biocortex_frontier`: explicit reminder that discovered selection is
  open and not claimed.

## Boundary

This tool is read-only. It does not:

- run BioCortex
- include raw query text, memory keys, or memory content
- write memory rows or graph edges
- approve runtime influence
- change `memory_search` order
- change `session_bootstrap` selection
- claim substrate-discovered retrieval selection

The output is intended for review packets, offline comparison, and later
evidence-gated T6 planning.

## Verification

Focused tests cover:

- The shadow packet exposes schema
  `agent_bridge.memory_biocortex_shadow_trial.v0`.
- The tool reports `read_only=true`, `runs_biocortex=false`, and
  `changes_memory_search_order=false`.
- Baseline, graph, suppression, and advisory rows use hashes only.
- Raw memory keys and content snippets do not appear in the serialized payload.
- The current BioCortex frontier explicitly keeps
  `discovered_selection_claimed=false`.
- Codex-essential policy exposes `memory_biocortex_shadow_trial`.

Commands:

```bash
cargo test -p ab-bridge memory_biocortex_shadow_trial -- --nocapture
cargo test -p ab-bridge tool_policy_codex_essential_ -- --nocapture
```

## Next Step

T6 should only consider ranking or bootstrap influence if T5 produces repeatable
lift evidence under redaction, review, and rollback gates. Until then, AB keeps
`memory_search` and the Continuity Kernel as the default authority.
