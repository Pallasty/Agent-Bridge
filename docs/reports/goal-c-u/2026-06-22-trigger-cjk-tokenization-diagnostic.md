# Trigger-Aware Recall CJK Tokenization Diagnostic

Date: 2026-06-22

Worktree: `/Users/pallasting/Projects/agent-bridge-trigger-cjk-token-diagnostic`

Branch: `codex/trigger-cjk-token-diagnostic`

Verdict: `diagnostic_only`. This explains the #27 `nexus_wuxing_math` miss from
the 30-case trigger-aware corpus. It does not authorize runtime retrieval,
tokenizer, schema, or ranking changes.

## Source Anchors

| Anchor | Value |
|---|---|
| base commit | `7b578a17c5c37ffb97867c203aeddc8a47c8f97e` |
| harness | `crates/bridge/examples/trigger_recall_eval.rs` |
| prior report | `docs/reports/goal-c-u/2026-06-22-trigger-aware-recall-eval.md` |
| live DB | `/Users/pallasting/Library/Application Support/agent-bridge/state.db` |
| case | #27 `nexus_wuxing_math` |

## Observation

`cargo run -p ab-bridge --example trigger_recall_eval -- 27` shows:

```text
## intent_content

## intent_projected

## exact_projected
   1. nexus_wuxing_shengke_golden_ratio_survey_20260621 <== EXPECTED
```

The exact trigger path is healthy: the authored trigger is projected into
`fts_content`, replayable, and ranks the expected key at #1. The held-out
Chinese intent query returns no candidates in either content or projected mode.

## Diagnostic

The debug mode now prints sanitizer and unicode61 token diagnostics. For case
#27, the held-out query:

```text
五行生克的成熟数学模型、黄金比例控制网络和平衡靶调研结论在哪里
```

is tokenized by SQLite FTS5 `unicode61` as two long terms:

```text
五行生克的成熟数学模型
黄金比例控制网络和平衡靶调研结论在哪里
```

The target row contains related but non-identical long Chinese runs, including:

```text
五行生克成熟数学模型调研
黄金比例反馈控制网络
黄金比例五行控制网络
平衡靶
循环平衡环
```

Because `unicode61` has no Chinese word segmentation, the paraphrase query does
not share the exact long terms needed for FTS candidate retrieval. The trigger
text works because it carries shorter slash-separated anchors and English terms
such as `golden ratio` and `wuxing_dynamics`.

## Interpretation

This is a Chinese paraphrase/tokenization blind spot, not a trigger projection
bug:

- projection/replay works for the authored trigger;
- the 30-case corpus still shows projection lift overall;
- negative controls remain clean;
- the miss is isolated to held-out CJK intent phrasing under FTS tokenization.

## Non-Authorizations

This diagnostic does not authorize:

- changing production tokenizer behavior;
- adding a CJK segmentation dependency;
- changing runtime ranking or search order;
- widening candidate sets;
- reindexing memory;
- adding an MCP tool.

## Next Step

Keep this as evidence for a later retrieval-design decision. A future
eval-only slice can compare candidate visibility under one or more read-only CJK
normalization strategies, but only after defining fixed cases and negative
controls.
