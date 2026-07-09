# StructMemEval Accounting Normalizer

Date: 2026-07-09

Source base commit: `8345aa6a`

Run type: deterministic answer normalizer contract

Parent packet:

- `docs/reports/goal-c-u/2026-07-09-structmemeval-upstream-smoke.md`

AB planning anchors:

- Durable memory key: `structmemeval_accounting_normalizer_20260709`
- Forum thread: `design#119`, post `2965`

Upstream source:

- Repo: `https://github.com/yandex-research/StructMemEval`
- Pinned commit: `64d2c9b242deb394e3ef94a318868a55261e141b`
- Accounting sample: `benchmark/data/accounting/debt_tracker_10_1.json`

## Verdict

The accounting normalizer is ready as a local deterministic contract. It parses
settlement-style answer text into canonical transaction tuples and can compare
candidate answers to reference variants by exact canonical transaction set.

This is not a benchmark run. It does not call an LLM, import StructMemEval's
runner, install dependencies, change retrieval, or write Agent-Bridge memory.

## Landed Files

```text
scripts/structmemeval-accounting-normalizer.py
scripts/verify-structmemeval-accounting-normalizer.sh
docs/reports/goal-c-u/2026-07-09-structmemeval-accounting-normalizer.md
```

## Contract

```yaml
schema: agent_bridge.structmemeval_accounting_normalizer.v0
family: accounting
official_runner_import_allowed: false
third_party_runtime_dependencies: false
api_key_required: false
private_memory_export_allowed: false
writes_ab_store: false
raw_content_in_output: false
comparison_mode: exact_canonical_transaction_set
memory_rows_delta: 0
memory_edges_delta: 0
semantic_events_delta: 0
```

Supported deterministic grammar:

- `Alice -> Bob : 24.83 EUR`
- `Alice pays 24.83 EUR to Bob`
- `Alice pays Bob 24.83 EUR`
- `Alice owes Bob 24.83 EUR`
- `Bob receives 24.83 EUR from Alice`

Canonical transaction tuple:

```yaml
payer: Alice
payee: Bob
currency: EUR
amount_cents: 2483
amount: "24.83"
```

The helper aggregates duplicate payer/payee/currency tuples, sorts
transactions deterministically, and compares candidates by the SHA-256 of the
canonical transaction-set key.

## Verification

Commands:

```bash
python3 -m py_compile scripts/structmemeval-accounting-normalizer.py
bash -n scripts/verify-structmemeval-accounting-normalizer.sh
scripts/verify-structmemeval-accounting-normalizer.sh
git diff --check
```

The verifier is offline:

- creates a local StructMemEval-shaped accounting fixture;
- creates a temp SQLite store with sentinel rows in `memories`,
  `memory_edges`, and `semantic_events`;
- normalizes three reference variants across the supported grammar;
- checks two exact candidate matches and one mismatch;
- asserts `memory_rows_delta == 0`, `memory_edges_delta == 0`, and
  `semantic_events_delta == 0`;
- asserts ambiguous candidate text fails;
- asserts output omits raw `content`, `question`, `reference_answer`, and
  `text` fields.

Manual upstream sanity run:

```bash
python3 scripts/structmemeval-accounting-normalizer.py --store-db "$tmp_db" --output "$tmp_json"
```

Against pinned source commit `64d2c9b242deb394e3ef94a318868a55261e141b`, the
helper normalized the default accounting sample with:

```yaml
case_id: accounting_10__1
source_sha256: 94cc1e965c43f3a2acb56a8e98306161174b77d34d548f486b6d9f8766d4adf9
query_count: 1
reference_variant_count: 3
reference_transaction_count_min: 2
reference_transaction_count_max: 2
memory_rows_delta: 0
memory_edges_delta: 0
semantic_events_delta: 0
```

## Limits

- The normalizer only supports `EUR` / `€` settlement transactions.
- It intentionally fails on answers that contain no supported transaction.
- It fails when unsupported leftover words remain after transaction parsing.
- It does not judge semantic equivalence beyond exact canonical transaction-set
  equality.
- It does not evaluate model quality, retrieval quality, or benchmark score.

## Decision

Use `scripts/structmemeval-accounting-normalizer.py` as the first deterministic
answer-comparison contract for StructMemEval accounting work.

The next safe lane is a pinned upstream accounting normalizer smoke that runs
this helper against the fixed accounting sample URL and records only hashes,
canonical tuples, counts, and no-write proof.
