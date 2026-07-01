# Memory Search Ranking Validation

Date: 2026-05-23

Status: implemented as an observability MVP. The bounded PageRank-style
centrality-prior experiment has now been completed offline and is `NO-GO`.
Do not wire centrality into `memory_search` ranking unless a later repaired,
store-resident corpus passes the reopen gates in
`docs/reports/goal-c-u/2026-07-01-centrality-prior-offline-no-go.md`.

## Question

Should Agent-Bridge add a PageRank-like algorithm to memory search?

## Live validation

Codex MCP telemetry over the current 7 day window shows that raw search latency
is not the main bottleneck at the present scale:

- `memory_search`: p95 about 1.2s in the filtered Codex audit window.
- `memory_get`: cheap relative to search.
- `work_memory`: about single-digit milliseconds.

The live memory graph is moderate in size, but not ready to become a global
rank prior:

- active memories: 925
- active non-skill memories: 441
- durable `memory_edges`: 829
- `memory_coactivation` pairs: 425
- max durable degree: 23

After implementing the read-only topology probe, the first local run returned:

- orphan count: 237 / 441 active non-skill memories
- orphan fraction: 0.537
- P4 evolved coverage: 142 / 441, fraction 0.322
- top non-skill hub degree: 21, fraction 0.048
- `pagerank_readiness`: `needs_graph_hygiene_before_rank_prior`

Current retrieval is already multi-signal:

- FTS5 / BM25 candidate retrieval.
- recency and access-count scoring through `memory_score`.
- importance weighting.
- feedback-kind boost.
- semantic cosine mode.
- hybrid FTS plus direct-neighbor graph expansion with RRF.
- coactivation rerank among the current result page.

## Decision

Do not add PageRank directly into `memory_search`.

PageRank-like centrality was useful enough to test as a possible bounded prior,
but the completed offline evaluation rejected it for the current store and
evidence base. Global centrality promoted hubs over peripheral targets, failed
the pre-registered lift gates, regressed leaf targets, and flipped sign across
edge direction. The current graph can still be observed and repaired, but
centrality is not approved as a ranking signal.

## MVP implemented

Add `memory_graph_topology`, a read-only MCP tool that exposes the existing
store-level `graph_topology()` snapshot:

- active non-skill total
- orphan count and fraction
- degree histogram
- top hubs
- evolved-edge coverage
- a coarse `pagerank_readiness` verdict

This gives Codex and other agents a cheap way to answer: "is the graph healthy
enough to test a centrality prior?" without mutating ranking.

The tool is registered as `Tier::Standard` and explicitly allowed in the
Codex-essential surface because search/ranking diagnosis is a core
Agent-Bridge self-tuning workflow and has no Codex-native equivalent.

## Graph Hygiene Guardrails

The first dry-run of `memory_link_orphans` after the topology probe confirmed
that graph hygiene can close many orphan gaps, but also exposed noise:

- default-ish run: 149 likely links from 178 eligible orphans
- stricter run with alert/snapshot/TTL tags skipped and threshold 0.85: 101
  likely links from 150 eligible orphans
- visible risk: repeated `alert-sync-failing-aio2-*` rows and broad
  `session_handoff_*` rows can become durable graph edges even though they are
  volatile or too generic for a future centrality prior

Follow-up implementation hardens `memory_link_orphans` before any non-dry-run
graph hygiene:

- default threshold raised to 0.85
- default skip tags: `auto_curated`, `alert`, `ttl:7d`
- default skip kinds: `alert`, `work_memory`, `session_handoff`, `snapshot`
- candidates must have compatible concrete scopes by default
- one run will not write both directions of the same `relates` pair

All guardrails are configurable through the tool arguments. The defaults are
intentionally conservative because false graph edges are more expensive than
missed edges once centrality is introduced.

First dry-run after the guardrail patch, using new defaults:

- examined: 415
- eligible orphans: 140
- candidate links: 85
- skipped by volatile tag: 78
- skipped by volatile kind: 14
- skipped duplicate symmetric pairs: 16

The sample no longer starts with alert/work-memory pairs; remaining candidates
are mostly durable stage/design chains. This is good enough for continued
dry-run review, but still not approval to run a write pass automatically.

## Future path

The former bounded-centrality experiment is closed as `NO-GO`; see
`docs/reports/goal-c-u/2026-07-01-centrality-prior-offline-no-go.md`. The
following shape remains only as reopen criteria for a later owner-approved,
store-resident corpus with enough centrality-connected golds:

1. Compute centrality offline or in a short-lived cache, not synchronously
   inside every `memory_search`.
2. Weight edge types separately. For example, `summarizes` and `part_of` should
   not behave like noisy `relates`.
3. Apply centrality as a small additive boost, capped around 5-10 percent of the
   final score.
4. Log before/after top-k diffs before enabling it by default.
5. Keep exact-key and fresh work-memory recall above graph centrality.

The first ranking changes should still be query-local repairs, such as better
token normalization and key/tag fallback for tool-like terms. The separate
semantic-ranking finding also points toward owner-reviewed weighting validation,
because additive bonuses can swamp cosine relevance in the opt-in semantic path.
Global centrality remains diagnostic only until a new evaluation proves it is
helping rather than amplifying hubs.
