# Memory Continuity T6 Influence Gate

Date: 2026-06-19

T6 adds a read-only gate for deciding whether BioCortex shadow evidence is
strong enough to request an opt-in influence experiment review. It does not
approve runtime influence.

## Interface

New MCP tool:

- `memory_biocortex_t6_influence_gate`

Inputs:

- `shadow_trials`: T5 `memory_biocortex_shadow_trial` packets.
- `relevance_lift_eval`: relevance-lift evidence from the BioCortex eval path.
- `redacted_evidence_aggregate`: redacted aggregate evidence packet.
- `min_shadow_trials`: default `3`.
- `min_evaluated_count`: default `10`.
- `min_mrr_lift`: default `0.001`.
- `max_worsened`: default `0`.

## Decision Model

The tool emits schema `agent_bridge.memory_biocortex_t6_influence_gate.v0`.

It returns `ready_for_opt_in_experiment=true` only when all gates pass:

- Enough T5 shadow packets are provided.
- T5 packets are read-only, redacted, and do not claim discovered selection.
- Relevance-lift evidence is completed, read-only, and does not change production
  retrieval order.
- Evaluated count, MRR lift, and regression thresholds pass.
- A redacted evidence aggregate is present and ready.

Even when this readiness is true, the tool still returns:

- `runtime_influence_approved=false`
- `ready_for_influence=false`
- `may_change_search_order_now=false`
- `changes_memory_search_order=false`

The next gate is human review before any runtime-influence decision.

## Boundary

This tool is read-only. It does not:

- run BioCortex
- call `memory_search`
- write memories, graph edges, authorization records, or approval packets
- include raw shadow packets, lift samples, queries, keys, or content
- approve runtime influence
- change retrieval or bootstrap order

## Verification

Focused tests cover:

- Missing relevance evidence and unsafe T5 frontier/raw flags block readiness.
- Passing shadow, lift, and redacted aggregate evidence enables only
  `ready_for_opt_in_experiment`, not runtime influence.
- Raw keys/content supplied in input are not echoed.
- Codex-essential policy exposes `memory_biocortex_t6_influence_gate`.

Commands:

```bash
cargo test -p ab-bridge memory_biocortex_t6_influence_gate -- --nocapture
cargo test -p ab-bridge tool_policy_codex_essential_ -- --nocapture
```

## Next Step

T6 output can feed a human review packet. Production ordering influence remains
blocked until a separate explicit review/authorization path grants it with
rollback and fail-open behavior.
