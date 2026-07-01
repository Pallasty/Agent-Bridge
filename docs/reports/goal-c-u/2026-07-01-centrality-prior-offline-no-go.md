# Centrality Prior Offline Evaluation No-Go

Date: 2026-07-01

Status: `CENTRALITY_PRIOR_OFFLINE_EVALUATED_NO_GO / NO_RUNTIME_CHANGE`

## Decision

Do not add a PageRank-style global centrality prior to `memory_search` ranking.

The completed offline evaluation found no reliable retrieval lift, meaningful
leaf-target regressions, direction fragility, and a mechanism mismatch between
global hub centrality and the store's real retrieval misses. Centrality remains
acceptable as read-only topology observability, but it is not approved as a live
or hidden ranking signal.

This report promotes the scratch owner packet into durable repo memory. It does
not change runtime code, schema, deployment, or MCP behavior.

## Why This Exists

The May ranking design left a narrow future path: if graph hygiene made topology
healthy enough, run a bounded centrality-prior experiment before any ranking
change. That experiment has now been completed offline against a frozen store
snapshot and a steelman corpus. Its result is a `NO-GO`, so the design status
needs to move from "possible future experiment" to "evaluated and rejected under
the current evidence."

## Evaluation Setup

Sources are under `/Data/CascadeProjects/.centrality_eval_scratch/`:

- `LOCKED_SPEC.md`
- `OWNER_PACKET.md`
- `eval_curated_results.json`
- `eval_steelman_results.json`
- `adversarial_verify_result.json`
- `FINDING_semantic_ranking_miscalibration.md`

Evaluation facts:

- Store snapshot: `state.frozen.db`
- Schema: v38
- Active memories: 579
- Embeddings: all active rows had 768-dimensional `gte-multilingual-base`
  embeddings
- Centrality graph: evolved-edge-only active subgraph, 1130 edges
- Excluded from boost: exact-key hits, `work_memory`, `session_handoff`,
  `alert`, and `snapshot`
- Candidate boost shape: rank-normalized PageRank times per-query cosine
  spread, capped at no more than 10 percent of the deciding gap
- Baseline: faithful Python replica of the store semantic formula:
  `cosine + 0.2 * importance + 0.1 * memory_score + feedback_boost`
- Tested directions and weights: forward and reversed PageRank at alpha 0.05
  and 0.10

## Core Findings

The real recall corpus had decayed since curation:

- 11 of 19 unique gold keys were no longer active in the store.
- 9 of 18 cases remained scorable.
- Only 1 of 8 present-active gold keys had nonzero evolved/causal degree.
- About half of active nodes were isolated in the evolved subgraph.

The surviving real retrieval targets were mostly peripheral. A global
centrality boost therefore helped central distractors more often than it helped
the gold answer. This is the central mechanism behind the `NO-GO`: it is a
hub-vs-leaf rank transfer, while realistic targets are frequently leaves.

## Curated Real Corpus

Scorable cases: 9

Baseline MRR: 0.023945013483423466

| Config | Delta MRR | 95% CI | Gold Improved / Worsened |
|---|---:|---|---:|
| reversed alpha=0.05 | -0.00009 | [-0.0002, -0.00002] | 0 / 6 |
| reversed alpha=0.10 | -0.00283 | [-0.0081, -0.0001] | 0 / 8 |
| forward alpha=0.05 | -0.00006 | [-0.0001, -0.00001] | 1 / 5 |
| forward alpha=0.10 | -0.00014 | [-0.0003, -0.00001] | 1 / 5 |

Every configuration had non-positive Delta MRR and more worsened than improved
gold ranks. On real targets the prior was neutral-to-harmful.

## Steelman Corpus

The steelman set was centrality-stratified to give the hypothesis its best fair
chance.

Baseline:

- Hub MRR: 0.152, R@10: 0.73
- Leaf MRR: 0.087, R@10: 0.20

| Config | Hub Delta MRR | Leaf Delta MRR | Pooled Delta MRR | Beats Permutation Null |
|---|---:|---:|---:|---|
| reversed alpha=0.05 | +0.00092 | -0.00018 | +0.00037 | no |
| reversed alpha=0.10 | +0.00264 | -0.00166 | +0.00049 | no |
| forward alpha=0.05 | -0.00183 | -0.00026 | -0.00105 | no |
| forward alpha=0.10 | -0.00517 | -0.00444 | -0.00481 | no |

The reversed direction produced a small hub-only gain, but that gain was paid
for by leaf regressions and did not beat the permutation null. The forward
direction flipped the sign and harmed even hubs.

## Decision Gate Result

All pre-registered go conditions failed:

- Pooled confidence interval lower bound greater than zero: fail.
- Beats permutation null: fail.
- No control-stratum regression: fail.
- Robust across edge direction: fail.

The strongest rescue attempt was a per-candidate high-centrality gate with
reversed PageRank at alpha 0.10. It produced a pooled Delta MRR of about
+0.00373, but it still failed because it regressed leaf targets, sign-flipped
under forward direction, depended on a circular hub-label gate, and remained far
below the declared detectable-effect threshold.

## Implication

Global centrality is not the right next retrieval lever. The actual measured
retrieval issue is semantic ranking miscalibration: additive importance,
memory-score, and feedback bonuses can swamp cosine relevance in the opt-in
semantic path. The scratch finding estimates that rebalancing cosine versus
importance recovers roughly +0.31 hub MRR, around two orders of magnitude larger
than the best centrality rescue's +0.003.

That does not authorize a semantic ranking runtime change. It only redirects
future investigation toward owner-reviewed ranking-weight validation and
query-local repair, rather than PageRank-style global centrality.

## Runtime Boundary

This report does not authorize:

- PageRank, centrality, or graph-neighbor influence in live ranking
- hidden `memory_search` parameters that mutate order
- schema changes
- graph backfills
- automatic orphan linking
- semantic ranking-weight changes
- deployment

## Reopen Criteria

Centrality may only be reconsidered after a new owner-approved evaluation packet
exists with all of the following:

- a repaired, store-resident corpus of at least 40-60 cases;
- enough centrality-connected golds to avoid a by-construction floor-node test;
- explicit hub, leaf, exact-key, and fresh-work-memory guardrails;
- a permutation-null comparison;
- robust positive lift across edge direction and damping choices;
- zero material control-stratum regression;
- owner sign-off before any runtime source change.

Until then, centrality is read-only diagnostic signal, not ranking policy.
