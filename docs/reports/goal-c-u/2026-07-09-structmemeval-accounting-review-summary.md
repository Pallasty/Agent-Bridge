# StructMemEval Accounting Review Summary

Date: 2026-07-09

Source base commit: `cb0dd204`

Run type: compact human-review summary mode

Parent packet:

- `docs/reports/goal-c-u/2026-07-09-structmemeval-accounting-candidate-corpus.md`

AB planning anchors:

- Durable memory key: `structmemeval_accounting_review_summary_20260709`
- Forum thread: `design#119`, post `2972`

## Verdict

The accounting normalizer now has an explicit `--review-summary` mode for
compact human review. The default normalizer packet remains unchanged.

The summary mode is not a scoring lane. It reports canonical transaction
tuples, match/mismatch status, source hashes, and no-write deltas without
emitting raw case, reference, or candidate answer text.

## Landed Files

```text
scripts/structmemeval-accounting-normalizer.py
scripts/verify-structmemeval-accounting-review-summary.sh
docs/reports/goal-c-u/2026-07-09-structmemeval-accounting-review-summary.md
```

## Contract

```yaml
schema: agent_bridge.structmemeval_accounting_normalizer_review_summary.v0
source_schema: agent_bridge.structmemeval_accounting_normalizer.v0
comparison_mode: exact_canonical_transaction_set
official_runner_import_allowed: false
third_party_runtime_dependencies: false
api_key_required: false
private_memory_export_allowed: false
writes_ab_store: false
raw_content_in_output: false
memory_rows_delta: 0
memory_edges_delta: 0
semantic_events_delta: 0
```

Summary output includes:

- case id, source mode, case hash, byte count, query count, and reference
  variant count;
- aggregate candidate/reference counts;
- reference variant canonical tuple summaries;
- candidate canonical tuple summaries and exact-reference-match status;
- compact no-write proof.

Summary output omits:

- raw `content`, `question`, `reference_answer`, and `text` fields;
- raw candidate and reference strings;
- local `source` path;
- SQLite `store_db`, `before`, and `after` row-count details.

## Verification

Commands:

```bash
python3 -m py_compile scripts/structmemeval-accounting-normalizer.py
bash -n scripts/verify-structmemeval-accounting-review-summary.sh
scripts/verify-structmemeval-accounting-review-summary.sh
git diff --check
```

The verifier:

- uses the checked-in candidate corpus fixture;
- creates only temp case/output/SQLite files;
- runs the normalizer with `--review-summary`;
- checks schema, compact case fields, counts, candidate match status, canonical
  tuple presence, and zero deltas;
- asserts raw fixture strings and internal temp store details are omitted.

## Decision

Use `--review-summary` for human-readable review of accounting normalization
behavior before designing any scoring gate.
