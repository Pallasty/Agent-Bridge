# Free Recall Strategy R1 — Frozen-Snapshot Replay Preregistration

Date: 2026-07-21

Status: **PREREGISTERED / READ-ONLY REPLAY ONLY / NO RUNTIME AUTHORITY**

Parent exploration:
`docs/design/FREE_RECALL_MEMORY_STRATEGY_EXPLORATION_2026_07_21.md`

## 1. Question

R0 showed that a task-aware strategy selector can beat any one global strategy
on a public-synthetic mechanism fixture, but its text-only router failed the
paraphrase challenge. R1 asks whether strategy specialization has value on the
existing real curated Agent-Bridge evaluation fixtures:

> Under one frozen store snapshot and one fixed candidate budget, do temporal
> adjacency or graph expansion improve the task class they are supposed to
> serve, and can a query-text router capture that value without labels?

This is a replay experiment, not a runtime implementation.

## 2. Ground-truth preflight

The current Mac store is not eligible: only 4 of the 65 referenced fixture keys
exist and only 3 are active. Running there would measure corpus drift, not
retrieval strategy.

Read-only node checks found:

- `aio2`: sampled fixture anchors absent;
- `tb14`: all 65/65 fixture keys present and active.

R1 therefore uses a read-only SQLite online backup of the tb14 store. The
source connection must use `mode=ro` plus `PRAGMA query_only=ON`, and its
`total_changes` must remain zero. The base snapshot is private and temporary.
No database bytes, memory contents, or uncommitted fixture labels may enter the
repository.

Before replay, the runner must recheck all 65 expected keys. Any missing or
non-active key stops the run with `CORPUS_DRIFT_BLOCKED` and emits no strategy
verdict.

## 3. Frozen fixture inputs

| Fixture | Task class | Cases | SHA-256 |
|---|---|---:|---|
| `retrieval_pairs.json` | conditional | 9 | `26dd84b7caab2161adab3cef3c6c41e5e747cc1f7ab38ec15d16e7d4abd9a362` |
| `relational_pairs.json` | relational / causal | 22 | `a9fbb4b5d33c26843966b24e5d1c2f399e8aa88ae62ef4cfb178b44557e44375` |
| `synthesis_queries.json` | exhaustive synthesis | 13 | `b4eb4bc7b977c4df3773478eed68c763331a2e161088e4f27485cc2bc04b5522` |

No cases may be added, removed, relabelled, or rewritten after preregistration.

## 4. Common retrieval budget

- Candidate budget: 20 keys per arm and query.
- Search modes: `fts`, `hybrid`, and `semantic`.
- `multimode_rrf` and every expansion arm may make exactly three
  `memory_search` calls, one per mode.
- RRF constant: 60.
- Expansion seeds: top 10 RRF candidates.
- Remaining expansion slots: 10.
- BioCortex retrieval: forced disabled.
- Seed/perception boost: forced disabled.
- Traffic class: `eval`.
- Missing scope/target/metadata: abstain or retain the baseline; never widen
  silently.

## 5. Arms

### A0 — `content_hybrid`

One `memory_search(mode=hybrid, limit=20)` call. It is the low-cost global
content baseline.

### A1 — `multimode_rrf`

RRF-fuse top-20 pages from FTS, hybrid, and semantic search into one fixed
top-20 page. This is the strongest global relevance control and the primary
single-arm comparator.

### A2 — `temporal_adjacency`

Keep the top 10 A1 seeds. Fill slots 11–20 with nearest active predecessor and
successor records by `created_at`, restricted to the seed's exact scope.
Deterministic channel order: seed rank, distance, predecessor before successor,
then key.

Important limitation: the current schema has no canonical `episode_id` column.
A2 is a temporal-context proxy, not a claim that AB already has the paper's
index scaffold.

### A3 — `graph_expansion`

Keep the top 10 A1 seeds. Fill slots 11–20 from existing, active, same-scope
neighbors in this fixed channel order:

1. `related_keys`;
2. active keys cited in record content;
3. non-coactivation `memory_edges`, traversed in either direction.

No two-hop traversal and no unbounded neighborhood are allowed.

### A4 — `text_router`

Uses query text only and the unchanged R0 generic rules:

- explicit why/cause language -> graph;
- explicit complete/all/order language -> temporal;
- otherwise -> multimode relevance.

Fixture class, gold keys, expected keys, notes, and edge labels are forbidden
router inputs.

### A5 — `oracle_router_upper_bound`

Scoring-only upper bound:

- conditional -> A1;
- relational/causal -> A3;
- exhaustive synthesis -> A2.

A5 is not implementable runtime evidence and can never satisfy a shipping gate.

## 6. Scoring

Per case:

- conditional and relational: `hit@10` against `expected_any` or
  `expected_key`; reciprocal rank is informational;
- synthesis: `set_recall@20` over the frozen gold set;
- regression rows: golds present in A1 but lost by A2/A3 at the same budget;
- cost: search calls, returned candidates, expansion candidates considered,
  wall time, and p95 per arm.

Aggregate each task class separately, then macro-average the three class means
so the 22 relational cases cannot dominate the 9 conditional cases.

## 7. Preregistered decision gates

### Strategy-potential gate

`oracle_router_upper_bound >= best_global_arm + 0.05` on macro task score.

### Mechanism gates

- A2 synthesis score >= A1 synthesis score + `0.05`;
- A3 relational hit@10 >= A1 relational hit@10 + `0.05`;
- A2/A3 conditional score regression <= `0.02` when selected by A4;
- no cross-scope candidate and no live-store write.

### Router gate

- route accuracy >= `0.80`;
- A4 macro score >= best global arm + `0.05`;
- A4 macro score is no more than `0.05` below A5.

### Cost gate

- fixed top-20 output budget;
- A2/A3 p95 <= `2x` A1 p95 excluding one-time snapshot construction;
- no more than three search calls per query.

## 8. Interpretation and stopping rules

- If A5 fails the strategy-potential gate: stop this direction; no router work.
- If A5 passes but A2 fails: record that current temporal metadata is
  insufficient and design an explicit episode/session scaffold before training.
- If A5 passes but A4 fails: strategy specialization remains promising, but
  rule routing is falsified; a separately reviewed intent-classification lane
  may follow.
- If graph gains require unbounded fanout: stop; existing traversal evidence
  already showed the context-cost hazard.
- No result authorizes changes to `memory_search`, `session_bootstrap`, graph
  writes, coactivation, BioCortex, deployment, or production defaults.

## 9. Aggregate-only result contract

The committed result may contain:

- fixture IDs and hashes;
- binary/source/snapshot hashes;
- case IDs, arm ranks, counts, timings, and aggregate metrics;
- missing/non-active key counts;
- explicit negative-authority fields.

It must not contain memory content, embeddings, raw DB paths from a private
environment, credentials, or a database copy.
