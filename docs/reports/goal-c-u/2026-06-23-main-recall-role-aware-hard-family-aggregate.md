# Main Recall Role-Aware Hard-Family Aggregate

Date: 2026-06-23
Host: `aio2`
Worktree: `/Data/CascadeProjects/agent-bridge`
Base: `769f514` (`test(memory): add case8 remote-session eval assembler`)
Scope: eval-only; no runtime implementation

## Why

The case #2 production review packet required a named eval aggregate mode before
any runtime flag is designed:

```text
Add a named eval-only aggregate row that includes role-aware case #2 and #8.
```

This slice adds that row to `recall_eval` while preserving the production
boundary: no default `memory_search`, MCP search, schema, tokenizer, graph,
semantic, or runtime ranking path changes.

## What Changed

`crates/bridge/examples/recall_eval.rs` now prints:

```text
## Eval-only role-aware hard-family aggregate
```

The aggregate denominator is intentionally narrow and explicit:

- case #2 `tool-surface`;
- case #8 `remote-session`.

It prints two rows:

- `strict_projected_families`: strict durable projected candidates before
  role-aware sorting;
- `role_aware_hard_families`: the eval-only role-aware result for the same
  implemented hard families.

It also prints per-family ranks and candidate counts, so missing local evidence
cannot be hidden inside the aggregate.

## Local Validation Context

Command:

```sh
cargo run -p ab-bridge --example recall_eval
```

Harness identity:

```text
baseline db source: default_db_path (live local store)
store fingerprint: pinned=false active=450 edges=562 newest=1782208999
embed backend: all-MiniLM-L6-v2
```

This is an Aio2 live-store smoke run, not the canonical pinned Mac snapshot.

## Aio2 Live Result

```text
## Eval-only role-aware hard-family aggregate
  mode                              n     R@1     R@5    R@10     MRR
  strict_projected_families         2   0.000   0.000   0.500   0.056
  role_aware_hard_families          2   0.500   0.500   0.500   0.500
```

Family detail:

```text
#2 tool-surface   strict=— role_aware=— strict_candidates=0 role_candidates=0
#8 remote-session strict=9 role_aware=1 strict_candidates=10 role_candidates=9
```

Interpretation:

- #8 is recovered by the remote-session role-aware assembler.
- #2 is not available in this Aio2 live baseline, so the aggregate honestly
  reports a miss instead of importing the pinned Mac result.
- The aggregate row therefore proves the measurement shape, not production lift
  on the canonical frozen baseline.

## Meta-Evidence Hygiene

After saving the #8 report memory, the Aio2 live store began surfacing
`main_recall_case8_remote_session_eval_assembler_20260623` as a remote-session
candidate. This is expected drift on a live store, and it is exactly why the
canonical gate needs a frozen `AB_BASELINE_DB`.

The role-aware classifiers now treat `main_recall`, `eval_assembler`,
`production_review`, and `review_packet` rows as diagnostic/meta evidence and
exclude them by default unless the query explicitly asks for diagnostic/meta
context.

## Decision

The named eval aggregate row is landed as a measurement contract:

- denominator is explicit: implemented role-aware hard families only;
- per-family ranks expose missing local evidence;
- production default remains NO-GO;
- frozen snapshot replay remains required before runtime-flag design.

Next gate:

1. Replay `recall_eval` with the pinned Mac `AB_BASELINE_DB` so #2 and #8 are
   evaluated on the same frozen baseline.
2. Then proceed to read-only snapshot open hardening.
