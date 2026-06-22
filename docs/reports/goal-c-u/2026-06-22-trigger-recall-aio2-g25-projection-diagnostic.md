# Trigger-Aware Recall Aio2 G25 Projection Diagnostic

Date: 2026-06-22

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Scope: diagnose the only aio2-native mini-corpus projected miss:
`aio2_lswr_g25_store_write`.

Verdict: `fallback_suppressed_by_nonempty_precise_result`. The miss is not
caused by missing projected text, missing trigger projection, or CJK
tokenization. It is caused by the eval harness search contract: the OR query is
only used when the precise query returns zero rows. On `projected_fts`, the
precise query returns one distractor row, so the OR query that would recover the
expected row is never used.

## Harness Change

`crates/bridge/examples/trigger_recall_eval.rs` now supports:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --debug-aio2-native 3
```

The mode is read-only and scratch-only:

- opens the selected DB read-only;
- builds the same in-memory `content_fts`, `projected_fts`, and
  `projected_cjk_fts` scratch tables;
- prints sanitized precise and OR MATCH expressions;
- compares content/projected precise and OR result sets;
- prints intent-query token overlap for the expected row in both authored
  `content` and projected `fts_content`;
- performs no `memory_get`, no `memory_search`, no writes, no reindexing, and
  no runtime ranking changes.

## Case

Case:

```text
id:      aio2_lswr_g25_store_write
query:   LSWR G25 store write execution preflight landed output only plan next gate
trigger: When continuing LSWR verified outcome ingestion gates after G25 store-write execution preflight.
expect:  lswr_verified_outcome_ingestion_store_write_execution_preflight_landed_20260620
```

Sanitized intent query:

```text
precise: LSWR* G25* store* write* execution* preflight* landed* output* only* plan* next* gate*
OR:      LSWR* OR G25* OR store* OR write* OR execution* OR preflight* OR landed* OR output* OR only* OR plan* OR next* OR gate*
```

Expected-row query-term overlap:

| Body | Chars | Query Terms Present | Missing |
|---|---:|---:|---|
| `content` | 2055 | 11 / 12 | `plan` |
| `fts_content` | 2173 | 11 / 12 | `plan` |

This rules out a simple "projection removed the needed terms" explanation:
`content` and `fts_content` have the same intent-query term coverage.

## Search Matrix

| Probe | First Expected Rank | Observation |
|---|---:|---|
| content intent precise | no hit | all 12 terms are too strict because `plan` is absent |
| content intent OR | 1 | OR fallback recovers the expected row |
| projected intent precise | no hit | returns one G26 distractor, not the expected row |
| projected intent OR | 1 | OR would recover the expected row |
| projected trigger precise | 1 | exact trigger replay is healthy |
| projected trigger OR | 1 | exact trigger OR is also healthy |

The effective `intent_projected` miss happens because the current `search()`
helper uses OR only when the precise result set is empty. For this case:

- `content_fts` precise returns empty, so OR fallback runs and the expected row
  ranks #1;
- `projected_fts` precise returns one distractor
  (`lswr_verified_outcome_ingestion_write_evidence_preflight_landed_20260620`),
  so OR fallback is suppressed and the expected row is never considered;
- `projected+cjk_acc` also misses because it only invokes the CJK fallback when
  projected search returns empty, and projected search returned the distractor.

## Interpretation

The aio2-native mini-corpus result should not be read as "projected text is
worse than content" in a broad sense. The narrower finding is:

1. projected trigger replay is healthy for this row;
2. held-out intent query terms are present in both content and projection;
3. strict precise matching can return a plausible distractor;
4. empty-only OR fallback can suppress the OR candidate set that contains the
   expected row.

This is a retrieval-eval contract issue, not evidence for a production ranking
change.

## Verification

Commands:

```bash
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --debug-aio2-native 3
```

Results:

| Check | Result |
|---|---|
| rustfmt | pass |
| example tests | pass, 10 passed |
| debug-aio2-native #3 | pass, finding above |

Existing unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name;
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

## Decision

Keep the line read-only. Do not change production `memory_search`.

This diagnostic does not authorize:

- production ranking or search-order changes;
- tokenizer/schema migrations;
- memory reindexing;
- candidate-set widening in production;
- semantic expansion;
- graph/PageRank influence;
- memory sync/import;
- memory writes;
- GHP-1b dry_run=false materialization.

## Next Slice

Add an eval-only comparison mode for candidate-set assembly:

1. current `precise_else_OR`;
2. `precise_plus_OR_union` with deterministic de-duplication;
3. `precise_then_OR_if_expected_missing` for diagnosis only.

Then split negative controls into:

- unrelated controls that should not retrieve any corpus gold keys;
- policy/intent adversarial controls that may retrieve relevant memories but
  should be rejected by a later acceptance layer.

Only after that split should semantic or policy-aware acceptance be compared
against projected FTS.
