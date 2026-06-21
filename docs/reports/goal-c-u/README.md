# Goal C U Reports

This directory contains report-first `U` runs for Goal C controlled recursive
self-improvement.

`U` is the standing utility surface for one question:

> Did this proposed change improve externally anchored continuity, or did it
> only add another internal gate or surface?

These reports are intentionally documents first. A report must not add an MCP
tool, mutate runtime state, change retrieval order, write memory, or authorize
an executor.

## Report Contract

Each report should include:

1. Source commit, deployed/runtime anchor, timestamp, and host.
2. Board window read, especially thread #120 when available.
3. Recall or cold-start metrics with explicit host and embedding model.
4. LSWR-H1 state: absent, design-only, run failed, run passed, or stale.
5. L6 falsified or shelved state.
6. BioCortex offline/runtime boundary state.
7. Tool atlas and dispatch audit snapshot.
8. Readiness or lifecycle snapshot.
9. Event-spine chain verification and chain head.
10. Work-memory or scratchpad context used, if any.
11. Proposed actions with owner, anchor, falsifier, rollback path, and next
    decision.

## Verdict Values

- `actionable`: at least one proposed action has an owner, anchor, falsifier,
  rollback path, and next decision.
- `blocked`: a required anchor is missing or stale.
- `observe_only`: telemetry is useful, but no safe action follows.
- `stop`: a falsifier triggered and the lane should halt or revert.

## Boundaries

Reports can recommend future docs, scripts, tests, or implementation plans.
They do not by themselves approve:

- runtime candidate-set expansion;
- search-order changes;
- centrality, PageRank, or graph priors in live ranking;
- new MCP surfaces;
- approval-gated executors;
- automatic commit, push, or deploy behavior.
