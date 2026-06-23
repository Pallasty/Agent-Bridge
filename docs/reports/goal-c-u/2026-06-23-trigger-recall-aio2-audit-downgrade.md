# Trigger Recall Aio2 Audit Downgrade

Date: 2026-06-23

Scope: downgrade the legacy aio2 baseline acceptance audit from a Stage-2 hard
gate to stale live telemetry when its host-local corpus is missing phantom gold
rows.

## Why

`--aio2-baseline-acceptance-audit` depended on `AIO2_NATIVE_CORPUS`, whose first
expected key is:

```text
lswr_verified_outcome_ingestion_apply_writer_gates_landed_20260620
```

Read-only checks on Mac/aio2 evidence showed that this key and nearby
`%outcome_ingestion_apply_writer%` rows were absent from live DBs and checked
backup/recovery DBs. Board review #4009 further classified the problem as a
phantom-gold audit contract rather than a recoverable normal corpus refresh.

## What Changed

`--aio2-baseline-acceptance-audit` now behaves as live telemetry:

- if `AIO2_NATIVE_CORPUS` is present and ready, it runs the existing baseline
  acceptance audit but labels the result as telemetry-only;
- if the corpus is missing, it prints a `stale_corpus_not_gate` report and exits
  successfully instead of acting as a hard Stage-2 blocker;
- `--check-aio2-native` remains the explicit hard corpus-readiness check.

The deterministic code-regression gate remains:

```text
cargo run -p ab-bridge --example trigger_recall_eval -- --portable-stage2-fixture
```

## Boundary

This does not:

- mutate memory DB rows;
- restore or reconstruct missing LSWR rows;
- change default `memory_search`;
- authorize production `enforce_hold`;
- deploy or install anything;
- change MCP tool exposure;
- touch GTE/embedder flag-day work.

## Expected Output Shape

When the aio2 corpus is missing, the legacy audit reports:

```text
status:                   stale_corpus_not_gate
hard_gate_authority:      false
```

and ends with:

```text
eval_only: true; aio2 baseline acceptance audit is stale telemetry, not a Stage-2 hard gate or production approval.
required_gate: use --portable-stage2-fixture for deterministic code-regression proof, or repair aio2 live corpus with provenance before using live telemetry for policy claims.
```

## Remaining Production Gate

Production `enforce_hold` remains off. Any production claim still needs a real
held-out policy-benefit evaluation over a non-phantom corpus, not just a
portable code-regression fixture.
