# StructMemEval Accounting Upstream Normalizer Smoke

Date: 2026-07-09

Source base commit: `1e9d2656`

Run type: network smoke for pinned upstream accounting normalizer

Parent packet:

- `docs/reports/goal-c-u/2026-07-09-structmemeval-accounting-normalizer.md`

Upstream source:

- Repo: `https://github.com/yandex-research/StructMemEval`
- Pinned commit: `64d2c9b242deb394e3ef94a318868a55261e141b`
- Accounting sample: `benchmark/data/accounting/debt_tracker_10_1.json`

## Verdict

The deterministic accounting normalizer now has a repeatable network smoke
against the pinned upstream sample. The smoke confirms the helper can normalize
the real upstream reference variants into canonical transaction tuples while
preserving the no-write and no-raw-content boundaries.

This is not a benchmark run and does not claim model, retrieval, or scoring
performance.

## Landed Files

```text
scripts/verify-structmemeval-accounting-upstream-smoke.sh
docs/reports/goal-c-u/2026-07-09-structmemeval-accounting-upstream-smoke.md
```

## Smoke Result

```yaml
schema: agent_bridge.structmemeval_accounting_normalizer.v0
source_head: 64d2c9b242deb394e3ef94a318868a55261e141b
family: accounting
case_id: accounting_10__1
source_sha256: 94cc1e965c43f3a2acb56a8e98306161174b77d34d548f486b6d9f8766d4adf9
bytes: 5546
query_count: 1
reference_variant_count: 3
reference_transaction_count_min: 2
reference_transaction_count_max: 2
candidate_answer_count: 0
candidate_exact_match_count: 0
memory_rows_delta: 0
memory_edges_delta: 0
semantic_events_delta: 0
```

Pinned canonical variant hashes:

| variant | answer hash | canonical set hash | canonical transactions |
| ---: | --- | --- | --- |
| 1 | `2b179397d04d0ef059b8f313b795e125e45295213432c5a6f8a983b81cc7a785` | `f855f8eeb2cbd4691a4d7b16992bb29b6f41c38c0e5502e97a3cadca4844a2e5` | Alice -> Bob 24.83 EUR; Charlie -> Bob 218.33 EUR |
| 2 | `ccef00787906c0697588c0b99ca13be80c08914ddb536d3d143f2477cda27fef` | `b7340aa75181dc40d7947d7d965c23041c511008f05e74c5876a89ebb469afce` | Alice -> Bob 28.67 EUR; Charlie -> Bob 153.67 EUR |
| 3 | `af57899f6adf3524373f296af383c685e896da4f3829e85191e65ce67463a40b` | `305822d893ce37cce6f4862ad2e2c1f5086008a1c23e6c9dec34946daa9d684b` | Alice -> Bob 141.83 EUR; Alice -> Charlie 95.33 EUR |

## Verification

Commands:

```bash
python3 -m py_compile scripts/structmemeval-accounting-normalizer.py
bash -n scripts/verify-structmemeval-accounting-normalizer.sh
bash -n scripts/verify-structmemeval-accounting-upstream-smoke.sh
scripts/verify-structmemeval-accounting-normalizer.sh
scripts/verify-structmemeval-accounting-upstream-smoke.sh
git diff --check
```

The upstream smoke verifier:

- creates a temp SQLite store with sentinel rows in `memories`,
  `memory_edges`, and `semantic_events`;
- runs the normalizer against its default pinned upstream accounting URL;
- asserts source commit, case hash, byte count, summary counts, canonical
  answer hashes, canonical transaction tuples, and no-write deltas;
- asserts no raw `content`, `question`, `reference_answer`, `expected_answer`,
  `stated_fact`, or raw `text` fields are emitted.

## Decision

Use `scripts/verify-structmemeval-accounting-upstream-smoke.sh` as the
repeatable network check before changing the accounting normalizer grammar or
candidate comparison behavior.

The next safe lane is a tiny candidate-answer fixture corpus that exercises
accepted matches, accepted mismatches, and rejected ambiguous strings without
introducing benchmark scoring.
