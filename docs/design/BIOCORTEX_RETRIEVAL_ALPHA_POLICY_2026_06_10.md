# BioCortex Retrieval Alpha Policy

Date: 2026-06-10

## Decision

BioCortex retrieval side signals stay offline and read-only. The retrieval gate
now has two pre-registered alpha policies:

| policy | alpha | purpose |
|---|---:|---|
| `conservative` | 0.20 | Default smoke gate. Favors AB baseline embeddings and catches weak side signals. |
| `candidate-strong` | 0.80 | Candidate policy for side-signal review. May pass the current corpus, but requires holdout validation before runtime-boundary design. |

Manual alpha overrides are allowed for diagnosis only:

`BIOCORTEX_RETRIEVAL_BLEND_ALPHA=<0.0..1.0>`

Manual runs must not be cited as gate passes unless the alpha is later added to
this policy document.

## Current Evidence

The 35-query local corpus with 175 BioCortex side-signal rows produced:

| policy | alpha | MRR delta | regressions | verdict |
|---|---:|---:|---:|---|
| `conservative` | 0.20 | +0.01905 | 0 | fail |
| `candidate-strong` | 0.80 | +0.04286 | 0 | pass on current corpus only |

The first 33-query holdout corpus with 165 BioCortex side-signal rows produced:

| policy | alpha | baseline MRR | blended MRR | MRR delta | regressions | verdict |
|---|---:|---:|---:|---:|---:|---|
| `conservative` | 0.20 | 0.98485 | 1.00000 | +0.01515 | 0 | fail |
| `candidate-strong` | 0.80 | 0.98485 | 1.00000 | +0.01515 | 0 | fail |

The holdout result is a ceiling-effect finding: the side signal repaired the
only rank-2 case and reached perfect MRR, but the baseline was already too high
to satisfy a fixed +0.03 MRR lift threshold. This is enough to keep exploring
the side-signal path. It is not enough to approve runtime retrieval mutation.

The 36-query hard holdout corpus with 180 BioCortex side-signal rows produced:

| policy | alpha | baseline MRR | blended MRR | MRR delta | regressions | verdict |
|---|---:|---:|---:|---:|---:|---|
| `conservative` | 0.20 | 0.94444 | 0.97222 | +0.02778 | 0 | fail |
| `candidate-strong` | 0.80 | 0.94444 | 0.98611 | +0.04167 | 0 | pass |

The hard holdout avoids the first holdout's ceiling effect. It shows that
`candidate-strong` has measurable value on a harder independent corpus while
`conservative` remains a useful conservative smoke policy.

## Acceptance Rules

Before `candidate-strong` can authorize a runtime-boundary design, it must pass:

- the current 35-query corpus;
- a separate hard holdout corpus with at least 30 queries and 5 candidates each
  that avoids baseline ceiling effects;
- 100 percent side-signal coverage, or an explicit missing-row policy;
- 0 expected-document regressions;
- MRR@10 lift at least +0.03 on both current and holdout corpora;
- a pre-registered ceiling-aware rule if a holdout baseline starts above 0.97;
- human review of the top failures and any winner changes;
- documented p95 side-signal generation latency.

As of 2026-06-10, `candidate-strong` satisfies the current-corpus and hard
holdout metric gates, and it keeps `runtime_adapter_approved=false`. Human
review approved `candidate-strong` as an offline-only side-signal policy and
allowed a follow-up runtime-boundary design document. Runtime retrieval mutation
remains forbidden until a separate design and implementation are accepted.

Human review packet:

`docs/design/BIOCORTEX_RETRIEVAL_REVIEW_PACKET_2026_06_10.md`

Local offline side-signal generation timing:

| corpus | queries | side rows | wall ms | ms/query |
|---|---:|---:|---:|---:|
| current | 35 | 175 | 101.477 | 2.899 |
| easy holdout | 33 | 165 | 48.032 | 1.456 |
| hard holdout | 36 | 180 | 48.323 | 1.342 |

## Commands

Generate side-signal rows:

```bash
cargo run --quiet \
  --manifest-path /Programs/Users/Pallasting/Documents/CascadeProjects/biocortex-rs/Cargo.toml \
  --example ab_retrieval_side_signal_adapter \
  -- /Programs/Users/Pallasting/Documents/CascadeProjects/agent-bridge/crates/bridge/tests/fixtures/biocortex_retrieval_gate_corpus.jsonl \
  > /tmp/biocortex_retrieval_side_signal.jsonl
```

Run the conservative default:

```bash
CARGO_TARGET_DIR=/tmp/ab-target-retrieval-gate \
BIOCORTEX_RETRIEVAL_SIDE_SIGNAL=/tmp/biocortex_retrieval_side_signal.jsonl \
cargo run --quiet -p ab-bridge --no-default-features \
  --example biocortex_retrieval_gate_eval
```

Run the candidate policy:

```bash
CARGO_TARGET_DIR=/tmp/ab-target-retrieval-gate \
BIOCORTEX_RETRIEVAL_ALPHA_POLICY=candidate-strong \
BIOCORTEX_RETRIEVAL_SIDE_SIGNAL=/tmp/biocortex_retrieval_side_signal.jsonl \
cargo run --quiet -p ab-bridge --no-default-features \
  --example biocortex_retrieval_gate_eval
```

Run a holdout corpus:

```bash
CARGO_TARGET_DIR=/tmp/ab-target-retrieval-gate \
BIOCORTEX_RETRIEVAL_CORPUS=crates/bridge/tests/fixtures/biocortex_retrieval_gate_holdout_corpus.jsonl \
BIOCORTEX_RETRIEVAL_ALPHA_POLICY=candidate-strong \
BIOCORTEX_RETRIEVAL_SIDE_SIGNAL=/tmp/biocortex_retrieval_holdout_side_signal.jsonl \
cargo run --quiet -p ab-bridge --no-default-features \
  --example biocortex_retrieval_gate_eval
```

Run the hard holdout corpus:

```bash
CARGO_TARGET_DIR=/tmp/ab-target-retrieval-gate \
BIOCORTEX_RETRIEVAL_CORPUS=crates/bridge/tests/fixtures/biocortex_retrieval_gate_hard_holdout_corpus.jsonl \
BIOCORTEX_RETRIEVAL_ALPHA_POLICY=candidate-strong \
BIOCORTEX_RETRIEVAL_SIDE_SIGNAL=/tmp/biocortex_retrieval_hard_holdout_side_signal.jsonl \
cargo run --quiet -p ab-bridge --no-default-features \
  --example biocortex_retrieval_gate_eval
```

## Non-Goals

- No BioCortex `EmbeddingBackend` registration.
- No change to `memory_search`.
- No online reranking.
- No memory, embedding, coactivation, graph, or reward writes.
- No claim that `candidate-strong` generalizes before holdout validation.
- No after-the-fact acceptance rule change without documenting the ceiling
  effect and rerunning the affected corpus.
