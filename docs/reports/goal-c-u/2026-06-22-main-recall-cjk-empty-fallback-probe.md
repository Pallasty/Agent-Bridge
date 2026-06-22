# Main Recall CJK Empty-Fallback Probe

Date: 2026-06-22
Scope: read-only eval/report only
Base: layered on `4e13fed` (`test(memory): anchor recall hard-tier gate`)

## Why

Thread #120 post #3897 set the next gate for the CJK/runtime lane:
trigger-cohort improvements are useful, but a runtime retrieval proposal must
move the main `recall_eval` hard-tier anchor. The specific target is the fixed
18-case `recall_eval` corpus, especially the Chinese hard misses
#1/#2/#5/#9/#14.

This slice tests the smallest production-shaped candidate without changing
production retrieval: use the baseline FTS result unless it returns zero rows;
only then fall back to accepted CJK trigram candidates from a scratch in-memory
index.

## Change

`crates/bridge/examples/recall_eval.rs` now reports three additional read-only
probe modes:

- `fts+cjk`: raw scratch CJK trigram FTS over `COALESCE(fts_content, content)`;
- `fts+cjk_acc`: same candidate set, filtered by shared CJK trigram overlap;
- `fts_empty+cjk`: deployable-shape probe that keeps baseline FTS unless it
  returns zero rows, then uses accepted CJK candidates.

The scratch index writes only to an in-memory SQLite FTS table. It does not
change live `memory_search`, tokenizer/schema, reindexing, graph expansion,
semantic search, ranking, MCP tools, or memory rows.

## Verification

Commands:

```sh
rustfmt --edition 2024 --check crates/bridge/examples/recall_eval.rs
cargo test -p ab-bridge --example recall_eval -- --nocapture
cargo run -p ab-bridge --example recall_eval
```

Results on the Mac store:

| mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| fts | 0.278 | 0.556 | 0.611 | 0.361 |
| fts+graph | hit 0.611 | added 0 | rate 0.000 | MRR 0.361 |
| fts+cjk | 0.111 | 0.500 | 0.667 | 0.309 |
| fts+cjk_acc | 0.056 | 0.111 | 0.167 | 0.090 |
| fts_empty+cjk | 0.333 | 0.611 | 0.667 | 0.416 |
| hybrid | 0.111 | 0.444 | 0.500 | 0.226 |
| semantic | 0.000 | 0.111 | 0.111 | 0.056 |

Hard-tier result:

| mode/tier | n | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|---:|
| fts/hard | 8 | 0.000 | 0.250 | 0.250 | 0.067 |
| fts_empty+cjk/hard | 8 | 0.125 | 0.375 | 0.375 | 0.192 |

Per-case lift:

- `fts_empty+cjk` added one deployable-shaped hit over FTS misses: #1.
- raw/accepted CJK candidate probes can also see #17, but #17 is not recovered
  by the zero-row fallback because baseline FTS returns rows for that query.

## Read

This is the first main-corpus evidence that a CJK candidate visibility fix can
move the #3897 hard-tier gate without relying on graph or semantic ranking. The
lift is small but real:

- overall R@10 moves from 0.611 to 0.667;
- hard-tier R@10 moves from 0.250 to 0.375;
- #1 is recovered at rank 1 by the deployable-shaped fallback.

The probe also rejects overclaiming:

- replacing FTS with raw CJK is not acceptable; it loses baseline ordering.
- accepted CJK alone is too narrow; it misses most lexical/moderate cases.
- direct graph expansion still adds 0 hits.
- semantic e5 remains weak on this corpus.
- #2/#5/#8/#9/#14 remain unsolved, so this is not a complete continuity fix.

## Interaction With The Runtime Gate Anchor

This probe was reconciled after `4e13fed` added the standing hard-tier runtime
gate anchor to `recall_eval`. The combined output keeps the distinction explicit:

- production-mode hard-tier anchor remains unchanged:
  `fts=0.250`, `fts+graph=0.250`, `hybrid=0.000`, `semantic=0.125`;
- review targets #1/#2/#5/#9/#14 remain misses across the current production
  modes;
- `fts_empty+cjk` is reported separately as a candidate probe, where it recovers
  #1 and moves probe hard-tier R@10 to 0.375.

So the result is useful evidence for a future runtime proposal, not a production
continuity improvement claim by itself.

## Boundary

This report does not authorize production runtime changes. A future runtime
proposal must still add broader controls, especially project-adjacent CJK
negatives and a clear operator/off switch if it touches live retrieval.
