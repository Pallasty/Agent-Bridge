# Free Recall Strategy R1.1 — Frozen-Clock Result

Date: 2026-07-21

Status: **COMPLETE / STRATEGY-POTENTIAL GATE FAILED / STOP CURRENT ROUTING LANE**

Preregistration:
`docs/design/FREE_RECALL_STRATEGY_R1_1_FROZEN_CLOCK_ADAPTER_PREREGISTRATION_2026_07_21.md`

## 1. Executive result

The evaluation-only frozen-clock adapter removed the R1 reproducibility
blocker. All 264 independent observations (44 cases × 3 modes × forward and
reverse) returned exact-page-equal rankings, so the unchanged R1 evaluator was
allowed to score the six arms.

The substantive result is negative: the strongest global arm was
`multimode_rrf` at `0.793590`, while the oracle task-class selector scored only
`0.767094` (`-0.026496`). The preregistered strategy-potential gate required an
oracle lift of at least `+0.05`; it failed.

Per the stopping rule, do not train the text router and do not introduce
BioCortex for this strategy family. The present temporal-adjacency and graph
expansion proxies do not justify task-conditioned routing.

## 2. Reproducibility and custody

- fixture corpus: 65/65 keys present and active;
- cases: 44;
- frozen database-derived clock: `1784635233`;
- source total changes: `0 -> 0`;
- base snapshot SHA-256 before and after:
  `b46144a60efdca13929ef293e79989aa724b28c0523b8ff7bf8660b5a9ac8fc5`;
- adapter SHA-256:
  `4f7069105313fb3460240d9ff083745ae827de7beb3a8cdfbac1fa0cc337bb68`;
- aggregate private result SHA-256:
  `53259902d246889bf634080a205e22268d1a12275786098dd33e4218e615b5f2`;
- forward/reverse exact-page equality: PASS for FTS, Hybrid, and Semantic;
- result contains no memory content, query text, embeddings, database, or
  credentials.

The aggregate JSON remains an ephemeral evidence artifact. This document
records the public bounded result.

## 3. Arm scores

| Arm | Macro score | Retrieval | Relational | Synthesis | p95 ms |
|---|---:|---:|---:|---:|---:|
| `content_hybrid` | 0.786985 | 0.666667 | 0.954545 | 0.739744 | 37.209 |
| `multimode_rrf` | **0.793590** | 0.666667 | 1.000000 | 0.714103 | 121.964 |
| `temporal_adjacency` | 0.767094 | 0.666667 | 1.000000 | 0.634615 | 121.972 |
| `graph_expansion` | 0.767094 | 0.666667 | 1.000000 | 0.634615 | 121.971 |
| `text_router` | 0.785043 | 0.666667 | 1.000000 | 0.688462 | 121.964 |
| `oracle_router_upper_bound` | 0.767094 | 0.666667 | 1.000000 | 0.634615 | 121.972 |

The text router's route accuracy was `0.25`; its lift over the best global arm
was `-0.008547`.

## 4. Gate verdicts

| Gate | Verdict |
|---|---|
| strategy potential | FAIL |
| temporal mechanism | FAIL |
| graph mechanism | FAIL |
| conditional non-regression | PASS |
| router accuracy | FAIL |
| router lift | FAIL |
| router near oracle | PASS, but oracle itself is worse than global |
| temporal cost | PASS |
| graph cost | PASS |

Across all cases, temporal and graph expansion each added zero missing golds
and displaced four golds already present in the RRF page. Their cost was
bounded, but the mechanisms supplied no retrieval gain.

## 5. Interpretation

This does not falsify the paper's claim that a learned model can develop
multiple memory strategies. It falsifies a narrower implementation hypothesis:

> AB's current `created_at` adjacency and existing same-scope graph channels
> are sufficient strategy substitutes, and a query-text selector should switch
> among them.

They are not sufficient on this corpus. The likely missing representation is
closer to the paper's learned episodic/index scaffold: explicit episode or
list membership, item-to-context binding, and a retrieval policy trained or
adapted against recall outcomes. `created_at` proximity is not episode
membership, and generic AB graph edges are not a learned recall trajectory.

The correct next research move is therefore not router training. It is a new,
separately preregistered representation experiment that asks whether explicit
episode/session scaffolding can create mechanism lift before any selector is
trained. BioCortex remains unnecessary until such a mechanism produces a
measurable oracle advantage.

## 6. Claim boundary

R1.1 measures store-core FTS, Hybrid, and Semantic modes under a frozen clock.
It does not reproduce bridge-level exclusions, class quota, correction
co-surface, TTL projection, or telemetry. It therefore establishes a negative
core-strategy result, not tb14 end-to-end MCP performance parity.

No result authorizes merge, deployment, production retrieval changes,
BioCortex execution, or model training.
