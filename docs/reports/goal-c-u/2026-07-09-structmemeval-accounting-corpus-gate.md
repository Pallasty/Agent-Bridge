# StructMemEval Accounting Local Corpus Gate

Date: 2026-07-09

Source base commit: `5692cc6b`

Run type: local candidate-corpus gate, not benchmark scoring

Parent packet:

- `docs/reports/goal-c-u/2026-07-09-structmemeval-accounting-review-summary.md`

AB planning anchors:

- Durable memory key: `structmemeval_accounting_corpus_gate_20260709`
- Forum thread: `design#119`, post `2974`

## Verdict

The accounting normalizer now has a local corpus gate. The gate consumes the
checked-in accounting candidate corpus and the normalizer `--review-summary`
output, then emits a redacted PASS/FAIL packet.

This is not a StructMemEval benchmark score. It is a local fixture gate for
normalizer behavior.

## Landed Files

```text
scripts/structmemeval-accounting-corpus-gate.py
scripts/verify-structmemeval-accounting-corpus-gate.sh
docs/reports/goal-c-u/2026-07-09-structmemeval-accounting-corpus-gate.md
```

## Gate Contract

```yaml
schema: agent_bridge.structmemeval_accounting_corpus_gate.v0
fixture_schema: agent_bridge.structmemeval_accounting_candidate_corpus.v0
review_summary_schema: agent_bridge.structmemeval_accounting_normalizer_review_summary.v0
normalizer_schema: agent_bridge.structmemeval_accounting_normalizer.v0
scope: local_accounting_candidate_corpus_only
verdict: PASS
accepted_candidate_count: 7
accepted_pass_count: 7
rejected_candidate_count: 5
rejected_pass_count: 5
candidate_exact_match_count: 5
benchmark_performance_claim: false
structmemeval_official_runner_used: false
network_required: false
writes_ab_store: false
raw_content_in_output: false
memory_rows_delta: 0
memory_edges_delta: 0
semantic_events_delta: 0
```

The gate passes only when:

- all accepted candidates match their expected exact-match status, matched
  reference variant indices, transaction counts, and canonical tuples;
- all rejected candidates fail with their expected error class;
- no-write proof is checked and passes;
- no raw fixture strings are present in gate or review-summary output.

## Verification

Commands:

```bash
python3 -m py_compile scripts/structmemeval-accounting-corpus-gate.py
bash -n scripts/verify-structmemeval-accounting-corpus-gate.sh
scripts/verify-structmemeval-accounting-corpus-gate.sh
git diff --check
```

The verifier asserts:

- gate schema and source schemas;
- `PASS` verdict on 7 accepted and 5 rejected fixture expectations;
- compact no-write deltas are zero;
- raw fixture session, question, reference, and candidate strings are absent;
- the output does not contain benchmark-performance claim text.

## Decision

Use `scripts/structmemeval-accounting-corpus-gate.py` as the local guard before
changing accounting normalizer grammar or candidate comparison behavior.

Do not treat this gate as StructMemEval benchmark performance. A future
benchmark lane would need a separate owner-approved runner boundary, source
license review, and explicit score semantics.
