# Memory Search Ranking Validation

Date: 2026-05-23

Status: implemented as an observability MVP. Do not wire PageRank-style
centrality into `memory_search` ranking until the diagnostic surface has been
dogfooded.

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

Do not add PageRank directly into `memory_search` yet.

PageRank-like centrality is useful as a possible bounded prior, but it is risky
as a first move because global centrality can promote old hubs over fresh task
state. The first topology run also shows a high orphan fraction, so a global
rank prior would systematically ignore too much fresh or unlinked memory. The
current graph contains mixed edge semantics (`evolved`, `relates`, `supersedes`,
`summarizes`, `cofires`, and others), so centrality must be measured, cleaned,
and capped before it can become a ranking signal.

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

## Future path

If `memory_graph_topology` remains healthy over real use, the next experiment
should be a bounded centrality prior:

1. Compute centrality offline or in a short-lived cache, not synchronously
   inside every `memory_search`.
2. Weight edge types separately. For example, `summarizes` and `part_of` should
   not behave like noisy `relates`.
3. Apply centrality as a small additive boost, capped around 5-10 percent of the
   final score.
4. Log before/after top-k diffs before enabling it by default.
5. Keep exact-key and fresh work-memory recall above graph centrality.

The first ranking changes should still be query-local repairs, such as better
token normalization and key/tag fallback for tool-like terms. Global centrality
comes after the graph diagnostic proves it is helping rather than amplifying
hubs.
