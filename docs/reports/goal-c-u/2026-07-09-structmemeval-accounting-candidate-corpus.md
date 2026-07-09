# StructMemEval Accounting Candidate Corpus

Date: 2026-07-09

Source base commit: `7e22771a`

Run type: offline candidate-answer fixture corpus

Parent packet:

- `docs/reports/goal-c-u/2026-07-09-structmemeval-accounting-upstream-smoke.md`

AB planning anchors:

- Durable memory key: `structmemeval_accounting_candidate_corpus_20260709`
- Forum thread: `design#119`, post `2969`

## Verdict

The accounting normalizer now has a tiny local candidate-answer corpus that
pins comparison behavior before any scoring lane. The corpus is offline and is
not a benchmark score.

## Landed Files

```text
scripts/eval/fixtures/structmemeval_accounting_candidate_corpus.json
scripts/verify-structmemeval-accounting-candidate-corpus.sh
docs/reports/goal-c-u/2026-07-09-structmemeval-accounting-candidate-corpus.md
```

## Corpus Contract

```yaml
schema: agent_bridge.structmemeval_accounting_candidate_corpus.v0
normalizer_schema: agent_bridge.structmemeval_accounting_normalizer.v0
comparison_mode: exact_canonical_transaction_set
accepted_candidates: 7
exact_matches: 5
valid_mismatches: 2
rejected_candidates: 5
memory_rows_delta: 0
memory_edges_delta: 0
semantic_events_delta: 0
```

Accepted candidate classes:

- exact match with arrow transactions;
- exact match with `pays amount to` grammar;
- exact match with `receives amount from` grammar;
- exact match after duplicate payer/payee/currency aggregation;
- exact match with `EUR` amount prefix;
- valid parsed mismatch with one transaction;
- valid parsed mismatch with wrong direction.

The `EUR` prefix case also guards against overlapping grammar matches. Without
overlap suppression, `Alice pays EUR 28.67 to Bob` can be parsed both as
`pays amount to` and as `pays payee amount` with `payee=Eur`; this corpus
requires the intended single transaction.

Rejected candidate classes:

- no supported settlement transaction;
- unsupported non-`EUR` currency;
- unsupported leftover text after a parsed transaction;
- zero amount;
- payer and payee are the same person.

## Verification

Commands:

```bash
python3 -m py_compile scripts/structmemeval-accounting-normalizer.py
bash -n scripts/verify-structmemeval-accounting-candidate-corpus.sh
scripts/verify-structmemeval-accounting-candidate-corpus.sh
git diff --check
```

The verifier:

- reads `scripts/eval/fixtures/structmemeval_accounting_candidate_corpus.json`;
- writes only temp case/output/SQLite files;
- runs accepted candidates through the normalizer in one batch;
- asserts exact-match counts, matched reference variants, canonical
  transactions, and no-write deltas;
- runs rejected candidates one by one and asserts failure regexes;
- asserts raw fixture answer/reference strings are absent from helper output.

## Decision

Use this corpus as the local semantic guardrail before changing accounting
normalizer grammar or candidate comparison behavior.

The next safe lane is either to add a small normalization summary mode for
human review, or to design a scoring gate that consumes this corpus without
claiming StructMemEval benchmark performance.
