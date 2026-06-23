# Trigger Recall Portable Stage-2 Fixture

Date: 2026-06-23

Scope: implementation report for the deterministic Stage-2 fixture added to
`crates/bridge/examples/trigger_recall_eval.rs`.

## Why

The aio2 live audit currently depends on `AIO2_NATIVE_CORPUS`, but aio2 live DB
no longer contains the first expected LSWR key:

```text
lswr_verified_outcome_ingestion_apply_writer_gates_landed_20260620
```

That makes `--aio2-baseline-acceptance-audit` useful telemetry, but not a stable
code-regression gate while the live corpus is stale or missing provenance.

## What Changed

Added a new explicit eval mode:

```text
cargo run -p ab-bridge --example trigger_recall_eval -- --portable-stage2-fixture
```

This mode:

- runs before any live DB path is opened;
- builds repo-local fixture rows in memory;
- exercises the baseline acceptance shadow gate with accepted continuations,
  frontend/dashboard holds, write-bypass holds, and creative non-continuation
  holds;
- labels its output as `portable Stage-2 fixture (repo-local, no live DB)`;
- keeps the existing `--aio2-baseline-acceptance-audit` path unchanged.

## Boundary

This does not:

- mutate memory DB rows;
- restore or reconstruct missing LSWR rows;
- change default `memory_search`;
- authorize production `enforce_hold`;
- deploy or install anything;
- claim aio2 live-corpus quality.

## Verification

Targeted tests:

```text
cargo test -p ab-bridge --example trigger_recall_eval portable_stage2 -- --nocapture
# 2 passed
```

CLI fixture run:

```text
cargo run -p ab-bridge --example trigger_recall_eval -- --portable-stage2-fixture
# positive cases held: 0
# baseline false hits before shadow gate: 8
# baseline false hits after shadow gate: 0
```

## Remaining Production Gate

Production/deploy claims still require either:

- a passing aio2 live audit with restored/provenance-checked corpus; or
- owner-approved replacement of the hard aio2 live gate with this portable
  fixture plus live telemetry.
