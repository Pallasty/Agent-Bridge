# Trigger-Aware Recall Aio2 Native Inventory

Date: 2026-06-22

Host: Linux/Aio2 (`pallasting-ThinkBook-14-G5-IRH`)

Scope: continue the trigger-aware recall line after the aio2 corpus-source
preflight showed that the Mac-authored 30-case corpus is not present in aio2's
live memory DB.

Verdict: `aio2_native_trigger_inventory_ready`. The harness now has a reusable
read-only inventory mode that lists the active trigger-tagged rows available on
the current host. This gives the next recall slice a local evidence base without
importing or mutating memory.

## Harness Change

`crates/bridge/examples/trigger_recall_eval.rs` now supports:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --list-trigger-rows
```

The mode:

- opens the selected DB read-only;
- reports active rows, trigger rows, and projected rows;
- lists each trigger-tagged active row with key, kind, scope, content length,
  projected length, trigger text, and a short preview;
- performs no `memory_get`, no `memory_search`, no writes, no reindexing, and no
  runtime ranking changes.

## Aio2 Live Inventory

Command:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --list-trigger-rows
```

Result:

| Metric | Value |
|---|---:|
| DB | `/home/pallasting/.local/share/agent-bridge/state.db` |
| active rows | 441 |
| trigger rows | 13 |
| projected rows | 12 |
| read-only | yes |

The active trigger rows cluster into two useful local lines:

| Cluster | Rows | Notes |
|---|---:|---|
| LSWR verified-outcome ingestion | 6 | G21/G22 through G31 lineage and writer/apply gates |
| Goal C / graph hygiene / trigger recall | 7 | Controlled RSI Goal C, GHP-1/GHP-1b, and trigger-recall preflight state |

Two older rows still carry the pre-migration
`project:/Programs/Users/Pallasting/Documents/CascadeProjects/agent-bridge`
scope, while the rest carry
`project:/Data/CascadeProjects/agent-bridge`. That is useful corpus hygiene
signal for the next slice: scope migration affects local recall evaluation and
should be handled explicitly instead of hidden in ranking metrics.

## Interpretation

The previous `--check-corpus` result remains true: aio2 cannot evaluate the
Mac-authored 30-case trigger corpus because all 30 gold keys are absent from the
local DB.

This inventory adds the local alternative. A small aio2-native trigger corpus
can be curated from these 13 active trigger rows, with care to avoid making the
new self-referential evaluation rows dominate the corpus. The most stable first
slice is likely:

1. LSWR gate/lineage queries over the six LSWR rows;
2. Goal C / GHP queries over established rows before the trigger-recall
   self-observation rows;
3. explicit scope-migration controls for `/Programs` versus `/Data` scoped
   rows.

## Verification

Commands:

```bash
rustfmt --edition 2024 --check crates/bridge/examples/trigger_recall_eval.rs
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --list-trigger-rows
cargo check -p ab-bridge --examples
```

Results:

| Check | Result |
|---|---|
| rustfmt | pass |
| example tests | pass, 9 passed |
| list-trigger-rows | pass, 13 trigger rows listed |
| examples check | pass |

Existing unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name;
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

## Non-Authorizations

This report does not authorize:

- production `memory_search` changes;
- tokenizer/schema migrations;
- memory reindexing;
- runtime ranking or search-order changes;
- candidate-set widening in production;
- semantic expansion;
- graph/PageRank influence;
- memory sync/import;
- memory writes;
- GHP-1b dry-run=false materialization.

## Next Slice

Build an aio2-native mini corpus from the stable trigger inventory and add a
read-only eval mode that compares:

- default projected FTS ranking;
- trigger-aware projected query behavior;
- candidate-level CJK fallback only where the projected path misses;
- accepted false hits against local adjacent-control queries.

Keep the corpus preflight mandatory so missing or stale local rows produce an
honest setup failure instead of misleading recall metrics.
