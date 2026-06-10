# BioCortex Retrieval Benchmark Gate

Date: 2026-06-10

## Decision

BioCortex must pass an offline retrieval benchmark before it can influence
Agent-Bridge retrieval.

Substrate replay proves that AB events can become deterministic BioCortex
pulses. It does not prove stable embedding vectors, cosine ranking quality, or
recall lift.

## Read-Only Shape

The benchmark reads a fixed JSONL corpus and an optional BioCortex side-signal
JSONL file. It ranks candidates inside the benchmark process only.

It must not call mutating memory APIs, write embeddings, alter graph edges,
register a BioCortex `EmbeddingBackend`, or change `memory_search`.

Corpus row schema:

```json
{
  "id": "q_embedding_gate",
  "query": "Why should BioCortex not be added to EmbeddingBackend yet?",
  "expected_key": "embedding_gate",
  "candidates": [
    {
      "key": "embedding_gate",
      "content": "Do not add a runtime BioCortex EmbeddingBackend adapter yet..."
    }
  ]
}
```

Side-signal row schema:

```json
{"query_id":"q_embedding_gate","candidate_key":"embedding_gate","score":0.42}
```

`score` must be bounded to [-1.0, 1.0]. It is a benchmark-only side
signal, not an embedding replacement.

## Gate

The first gate is conservative:

- corpus size: at least 30 queries before a runtime decision;
- candidates: at least 5 candidates per query;
- side-signal coverage: at least 80 percent of query/candidate pairs;
- regressions: 0 expected-document rank regressions allowed;
- quality lift: MRR@10 improvement at least +0.03 over baseline;
- latency: side-signal generation p95 must fit a documented offline budget;
- review: human review is required even if metrics pass.

Passing this gate does not approve runtime mutation. It only authorizes a
follow-up runtime-boundary design.

## Corpus

The expanded fixture corpus is checked in at:

`crates/bridge/tests/fixtures/biocortex_retrieval_gate_corpus.jsonl`

It currently contains 35 queries with 5 candidates per query. The first six
queries come from the current BioCortex/Seed decisions:

| id | expected key | query focus |
|---|---|---|
| `q_shadow_digest` | `decision_shadow_only` | BioCortex kept out of default AB runtime dependency graph |
| `q_substrate_plan` | `substrate_replay` | What substrate replay proves and does not prove |
| `q_embedding_gate` | `embedding_gate` | Why no runtime `EmbeddingBackend` adapter yet |
| `q_seed_disposition` | `seed_legacy` | Seed kept as legacy/reference only |
| `q_checkout` | `biocortex_checkout` | Durable BioCortex checkout and adapter location |
| `q_benchmark_next` | `retrieval_benchmark` | Next safe step before retrieval influence |

This satisfies the initial corpus-size shape gate. The corpus is still a
project-local starter set, not a final statistically representative benchmark.

## Implementation Plan

1. Done: add a read-only `biocortex_retrieval_gate_eval` example.
2. Done: load corpus JSONL and optional side-signal JSONL.
3. Done: rank baseline candidates with the active AB embedding backend in-process.
4. Done: rank blended candidates with `baseline_cosine + alpha * side_signal`.
5. Done: add a BioCortex-side read-only side-signal generator:
   `/Programs/Users/Pallasting/Documents/CascadeProjects/biocortex-rs/examples/ab_retrieval_side_signal_adapter.rs`.
6. Done: make Linux native avatar Wayland dependencies opt-in behind
   `linux-native-avatar` so `ab-bridge --no-default-features` retrieval gate
   checks do not require host `pkg-config`/`xkbcommon`.
7. Done: run the AB eval example end to end with generated side-signal JSONL
   and record recall@1, recall@K, MRR@10, regressions, and coverage.
8. Done: improve the BioCortex side-signal scorer with row-local term
   weighting, key/content evidence, and light term normalization.
9. Done: pre-register alpha policies in
   `docs/design/BIOCORTEX_RETRIEVAL_ALPHA_POLICY_2026_06_10.md`.
10. Done: add a first holdout corpus and rerun both `conservative` and
   `candidate-strong`.
11. Done: add a hard holdout corpus that avoids the first holdout's ceiling
   effect. `candidate-strong` passes the hard holdout with 0 regressions.
12. Done: perform human review of remaining failures/winner changes and record
   side-signal generation latency.
13. Done: human review approved `candidate-strong` as an offline-only
   side-signal policy.
14. Next: keep `runtime_adapter_approved=false` and use
   `docs/design/BIOCORTEX_RETRIEVAL_RUNTIME_BOUNDARY_2026_06_10.md` as the
   boundary for any review-only runtime surface.

## Current Result

Final local run on 2026-06-10 used 35 queries, 5 candidates per query, and 175
BioCortex side-signal rows.

```json
{
  "baseline": {
    "mrr": 0.8809523809523809,
    "recall_at_1": 0.8,
    "recall_at_k": 1.0
  },
  "blended": {
    "mrr": 0.8999999999999999,
    "recall_at_1": 0.8285714285714286,
    "recall_at_k": 1.0
  },
  "mrr_delta": 0.01904761904761898,
  "regressions": 0,
  "side_signal_coverage": 1.0,
  "status": "side_signal_fails_offline_gate",
  "runtime_adapter_approved": false
}
```

The failure is useful: the current default blend improves recall@1 and does not
regress expected-document ranks, but it misses the required +0.03 MRR@10 lift.
Several weak cases are adjacent AB concepts where the side signal and baseline
disagree or the baseline gap is too large for the default alpha.

## Alpha Sensitivity

After improving the BioCortex side-signal scorer with row-local term weighting,
key/content evidence, and light term normalization, the default alpha still
fails but higher side-signal weight passes:

| alpha | MRR delta | regressions | status |
|---:|---:|---:|---|
| 0.10 | +0.00476 | 0 | `side_signal_fails_offline_gate` |
| 0.20 | +0.01905 | 0 | `side_signal_fails_offline_gate` |
| 0.40 | +0.02381 | 0 | `side_signal_fails_offline_gate` |
| 0.60 | +0.02857 | 0 | `side_signal_fails_offline_gate` |
| 0.80 | +0.04286 | 0 | `side_signal_passes_offline_gate` |
| 1.00 | +0.04286 | 0 | `side_signal_passes_offline_gate` |

This does not approve runtime retrieval mutation. The pre-registered policy is:
`conservative` remains the default alpha 0.20 smoke gate, and
`candidate-strong` uses alpha 0.80 as a review-only candidate policy. The next
review question is whether `candidate-strong` also passes a separate holdout
corpus without regressions.

## Holdout Result

The first holdout fixture is checked in at:

`crates/bridge/tests/fixtures/biocortex_retrieval_gate_holdout_corpus.jsonl`

It contains 33 queries with 5 candidates per query. BioCortex side-signal
generation produced 165 rows and 100 percent coverage.

| policy | alpha | baseline MRR | blended MRR | MRR delta | regressions | status |
|---|---:|---:|---:|---:|---:|---|
| `conservative` | 0.20 | 0.98485 | 1.00000 | +0.01515 | 0 | `side_signal_fails_offline_gate` |
| `candidate-strong` | 0.80 | 0.98485 | 1.00000 | +0.01515 | 0 | `side_signal_fails_offline_gate` |

This is not a runtime approval. It is a benchmark-design finding: a holdout
that starts near perfect MRR cannot satisfy the fixed +0.03 MRR lift gate even
when the side signal corrects the only non-top-ranked expected document.

## Hard Holdout Result

The hard holdout fixture is checked in at:

`crates/bridge/tests/fixtures/biocortex_retrieval_gate_hard_holdout_corpus.jsonl`

It contains 36 queries with 5 candidates per query. BioCortex side-signal
generation produced 180 rows and 100 percent coverage.

| policy | alpha | baseline MRR | blended MRR | MRR delta | regressions | status |
|---|---:|---:|---:|---:|---:|---|
| `conservative` | 0.20 | 0.94444 | 0.97222 | +0.02778 | 0 | `side_signal_fails_offline_gate` |
| `candidate-strong` | 0.80 | 0.94444 | 0.98611 | +0.04167 | 0 | `side_signal_passes_offline_gate` |

`candidate-strong` now passes the current corpus and the hard holdout metric
gates. Runtime mutation remains forbidden until human review and latency
evidence are recorded.

## Non-Goals

- No BioCortex `EmbeddingBackend` registration.
- No background learning loop.
- No writes to AB memory, embeddings, coactivation, or graph edges.
- No automatic `memory_search` reranking.
- No claim that substrate spikes equal retrieval quality.
