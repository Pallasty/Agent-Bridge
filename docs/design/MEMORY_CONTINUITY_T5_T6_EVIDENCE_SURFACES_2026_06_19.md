# Memory Continuity T5/T6 Evidence Surfaces

Date: 2026-06-19

## Context

The first live T5/T6 batch after MCP reconnect produced useful shadow evidence,
but T6 stayed blocked because two review inputs were missing:

- a formal redacted evidence aggregate;
- a relevance-lift eval that T6 can consume without raw per-sample memory keys.

The existing BioCortex relevance-lift evaluator is intentionally more detailed
and includes per-sample rows for offline review. That is too much payload for the
Codex-essential continuity path, where T6 should consume only aggregate fields.

## Change

Two read-only Standard MCP tools bridge the gap:

- `memory_biocortex_redacted_evidence_aggregate`
- `memory_biocortex_relevance_lift_summary`

`memory_biocortex_redacted_evidence_aggregate` consumes redacted
`memory_biocortex_shadow_trial` packets and emits the aggregate schema expected
by `memory_biocortex_t6_influence_gate`:

```text
agent_bridge.biocortex_retrieval.opt_in_redacted_evidence_aggregate.v0
```

It never calls `memory_search`, runs BioCortex, writes memory, echoes shadow
packets, exposes raw query/key/content, or changes retrieval order.

`memory_biocortex_relevance_lift_summary` calls the existing relevance-lift
yardstick, then strips per-sample rows and raw side-signal errors. It returns
only schema/status/verdict, sampling, metrics, caveats, safety, and a redaction
contract. It is still read-only and does not change production retrieval order.

## Boundary

These tools are evidence surfaces, not influence surfaces.

They do not:

- approve runtime influence;
- enable default retrieval-order changes;
- write approval records;
- write memory or graph edges;
- claim BioCortex discovered selection.

T6 remains the gate. Even when these two inputs are present and valid,
`memory_biocortex_t6_influence_gate` can only report readiness for human opt-in
experiment review. It still reports `runtime_influence_approved=false` and
`may_change_search_order_now=false`.

## Verification

Targeted validation for this slice after `/Data` space was recovered:

```bash
git diff --check
cargo test -p ab-bridge memory_biocortex_ -- --nocapture
cargo test -p ab-bridge tool_policy_codex_essential_exposes_extras_list -- --nocapture
```

The feature-branch commit hook also ran `cargo check -p ab-bridge --all-targets`.

The broad `cargo fmt --check` path is not a clean signal for this slice: the
same checkout contains pre-existing rustfmt diffs in unrelated files/regions.
This slice keeps edits localized and does not run whole-file formatting to avoid
mixing unrelated churn into the review.
