# Recall Eval Hard-Tier Runtime Gate Anchor

Date: 2026-06-22

Host: macOS (`maxiaodeMac-Pro.local`)

Worktree: `/Users/pallasting/Projects/agent-bridge-recall-hard-tier-anchor`

Branch: `codex/recall-hard-tier-anchor-gate`

Scope: eval-only hard-tier anchor for main `recall_eval`; no runtime retrieval
behavior change.

Verdict: `hard_tier_anchor_recorded`. Forum #3897 is accepted as the controlling
runtime gate: trigger-cohort gains do not count as continuity lift unless a
future runtime retrieval proposal also moves the main `recall_eval` hard tier,
especially #1/#2/#5/#9/#14.

## Harness Change

`crates/bridge/examples/recall_eval.rs` now prints a dedicated
`Runtime gate anchor (main recall_eval hard tier)` section after the honest read.
The section records:

- the gate contract: trigger-cohort-only improvement is decorative;
- hard-tier R@10 for `fts`, offline `fts+graph`, `hybrid`, and `semantic`;
- hard FTS misses;
- hard zero-row FTS misses;
- hard FTS+graph added hits over FTS misses;
- per-case status for the #3897 review targets #1/#2/#5/#9/#14, including FTS
  rank, raw FTS row count, offline FTS+graph rank, hybrid rank, and semantic
  rank.

This makes the #3897 review criterion reproducible from the existing eval
command instead of leaving it only as a forum guideline.

## Current Mac Baseline

Command:

```bash
cargo run -p ab-bridge --example recall_eval
```

Model selection:

```text
# auto-selected AGENT_BRIDGE_ONNX_MODEL=e5-small (store's dominant embedding_backend)
embed backend:   multilingual-e5-small
semantic:        ENABLED (real model confirmed)
```

Overall recall:

| Mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| `fts` | 0.278 | 0.556 | 0.611 | 0.365 |
| `hybrid` | 0.111 | 0.500 | 0.500 | 0.237 |
| `semantic` | 0.000 | 0.111 | 0.111 | 0.042 |

Hard-tier recall:

| Mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| `fts/hard` | 0.000 | 0.250 | 0.250 | 0.067 |
| `fts+graph/hard` | 0.000 | 0.250 | 0.250 | 0.067 |
| `hybrid/hard` | 0.000 | 0.000 | 0.000 | 0.000 |
| `semantic/hard` | 0.000 | 0.125 | 0.125 | 0.062 |

Runtime gate anchor output:

```text
## Runtime gate anchor (main recall_eval hard tier)
  contract: future runtime retrieval changes can claim continuity lift only if this main hard-tier anchor moves; trigger-cohort-only improvement is decorative.
  hard-tier R@10: fts=0.250 fts+graph=0.250 hybrid=0.000 semantic=0.125
  hard fts misses: 6 case(s) -> #1, #2, #5, #8, #9, #14
  hard zero-row fts misses: 2 case(s) -> #1, #2
  hard fts+graph added hits over fts misses: 0 case(s)
```

Review target status:

| Case | FTS | FTS Rows | FTS+Graph | Hybrid | Semantic | Query |
|---:|---:|---:|---:|---:|---:|---|
| #1 | miss | 0 | miss | miss | miss | 记忆系统应该追求记住更多,还是用更少上下文恢复正确状态 |
| #2 | miss | 0 | miss | miss | miss | 工具面太多了应该按什么维度归类收口,是直接删还是重新分级 |
| #5 | miss | 10 | miss | miss | miss | 怎么查看 sibling 推到远端的文件内容又不影响我的工作树 |
| #9 | miss | 10 | miss | miss | miss | agent-bridge 这个项目的核心愿景定位是什么 |
| #14 | miss | 10 | miss | miss | miss | biocortex 影子试验是只读的吗,会不会改默认检索顺序 |

## Interpretation

The main hard-tier anchor still shows the continuity problem that #3897 called
out:

- #1 and #2 are zero-row FTS misses, so they expose query-to-memory vocabulary
  bridging failure, not only bad ranking.
- #5/#9/#14 produce FTS candidates but none of the designated answers reach
  top 10 in any production retrieval mode.
- Offline FTS+graph adds zero hard-tier hits over FTS misses, so direct graph
  neighbor expansion is not enough on this current store.
- Semantic remains weaker than FTS on the main corpus, even with the correct
  e5-small model auto-selected for the Mac store.

Therefore, a future runtime retrieval change should be measured against this
anchor before it claims continuity improvement. The minimum meaningful movement
is recovering some of #1/#2/#5/#9/#14 or improving hard-tier R@k without
regressing the existing moderate/easy behavior.

## Verification

Commands:

```bash
rustfmt --edition 2024 --check crates/bridge/examples/recall_eval.rs
cargo test -p ab-bridge --example recall_eval -- --nocapture
cargo run -p ab-bridge --example recall_eval
```

Results:

| Check | Result |
|---|---|
| rustfmt | pass |
| example tests | pass, 5 passed |
| recall eval | pass, metrics above |

Existing unrelated warnings remained present:

- `ab-store` mixed-script confusable warning for the existing beta test name;
- `ab-bridge` warnings around `ToolPolicy` visibility and unused Option-E helper
  items.

## Non-Authority

This slice does not authorize:

- production `memory_search` changes;
- production ranking or candidate-order changes;
- tokenizer/schema migrations;
- memory reindexing;
- semantic expansion;
- graph/PageRank influence;
- new MCP tools;
- memory writes.

It only makes the hard-tier runtime gate visible and repeatable inside the
standing eval command.
