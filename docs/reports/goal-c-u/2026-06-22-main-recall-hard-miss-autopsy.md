# Main Recall Hard-Miss Autopsy

Date: 2026-06-22
Host: `maxiaodeMac-Pro.local`
Worktree: `/Users/pallasting/Projects/agent-bridge-main-recall-hard-miss-autopsy`
Branch: `codex/main-recall-hard-miss-autopsy-v1`
Base: `13fec8a` (`Merge remote-tracking branch 'github/master'`)
Scope: read-only eval/report only

## Why

Thread #120 post #3897 set the runtime recall gate around the fixed
`recall_eval` corpus, with the Chinese hard misses #1/#2/#5/#9/#14 called out
as the useful next target. The CJK empty-fallback probe later recovered #1, but
left #2/#5/#9/#14 unresolved and also showed that #8 is an interesting adjacent
case because semantic retrieval can see it while FTS/hybrid cannot.

This slice does not propose a runtime change. It classifies the remaining hard
misses so the next implementation slice can target a specific failure mode
instead of treating all misses as one tokenizer problem.

## Board Window

- #3897: runtime improvement must move the main `recall_eval` hard-tier anchor,
  especially #1/#2/#5/#9/#14.
- #3907: `fts_empty+cjk` recovered #1 only and moved hard R@10 from 0.250 to
  0.375, with no runtime authorization.
- #3909: another lane claimed `U` local refresh and `memory_save` schema
  ergonomics. That work is orthogonal to this report.
- #3910: this lane claimed a non-overlapping hard-miss autopsy: inspect
  #2/#5/#8/#9/#14 using `recall_eval <case>` and memory reads, write one report,
  make no runtime/search changes.

## Evidence Commands

```sh
for case_id in 2 5 8 9 14; do
  cargo run -p ab-bridge --example recall_eval -- "$case_id" \
    > "/tmp/ab-hard-miss-autopsy/case_${case_id}.txt" 2>&1
done
```

Expected memories and top candidates were then inspected with `memory_get` and
the generated `/tmp/ab-hard-miss-autopsy/case_*.txt` outputs.

## Summary

| Case | Query theme | Current behavior | Failure class | Next lever |
|---:|---|---|---|---|
| #2 | tool-surface taxonomy and retiering | FTS/hybrid return zero rows; semantic returns unrelated high-cosine cross-project memories | candidate absence for a direct CJK reference, not solved by the first CJK empty fallback | tool-surface alias/projection or query segmentation probe |
| #5 | read sibling-pushed file without touching worktree | FTS/hybrid return same-domain git/remote/worktree distractors; expected lesson is absent from top 10 | intent-specific lesson buried by broad vocabulary overlap | phrase/command-aware bridge for `git show origin/master:<path>` |
| #8 | inject instructions into a long-running remote agent session | FTS/hybrid miss; semantic ranks the expected decision at #2 | semantic rescue is real, but globally noisy | semantic-rescue gate with strict controls, not broad semantic blending |
| #9 | Agent-Bridge core vision | all modes miss the North-Star memory; FTS/hybrid prefer generic project/tool implementation memories | curated core-vision anchor gap | protected North-Star alias or explicit U dashboard anchor |
| #14 | BioCortex shadow trial read-only/order-safety | FTS/hybrid return many BioCortex/T5/T6 memories, but not the specific T5 read-only contract | version/specificity failure under newer same-domain memories | T5/version/read-only contract alias or specificity-aware rerank |

The miss set is therefore mixed:

- #2 is a candidate-visibility failure.
- #5 is an intent/phrase specificity failure.
- #8 is a semantic-rescue candidate, but not part of the original #3897 target
  list and not safe evidence for broad semantic mixing by itself.
- #9 is a curated-identity anchor failure.
- #14 is a versioned-contract specificity failure.

## Case Notes

### #2 Tool-Surface Taxonomy

Query:

```text
工具面太多了应该按什么维度归类收口,是直接删还是重新分级
```

Expected:

```text
reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618
```

The expected memory directly answers the query: it defines the eight tool-surface
classes and the policy that Agent-Bridge should retier or route surfaces instead
of deleting them. The current `recall_eval 2` output shows no FTS/hybrid
candidates for the expected memory, while semantic top candidates are unrelated
cross-project memories with saturated cosine scores.

This is not primarily a graph or rerank problem because the expected memory is
not entering the lexical candidate set. The previous `fts_empty+cjk` probe also
did not recover #2, so a plain CJK trigram fallback is insufficient. The next
useful slice should test whether a projection/alias layer can expose terms like
`tool surface`, `retier`, `8 class`, `收口`, `分级`, and `删除` without changing
runtime search order.

### #5 Git Show Without Pull

Query:

```text
怎么查看 sibling 推到远端的文件内容又不影响我的工作树
```

Expected:

```text
lesson_git_show_origin_master_read_without_pull_20260518
```

The expected lesson is precise: use `git show origin/master:<path>` to read a
sibling-pushed file without pulling or touching local WIP. FTS top candidates
are all plausible git/remote/worktree memories, including shared checkout churn,
remote session handoff, master push ownership, and multi-agent shared worktree
contention.

This is not candidate starvation across the whole topic. It is an
intent-specific lesson losing to broader vocabulary overlap. A future probe
should test whether command-shaped phrases and exact operational intents can be
recognized without simply boosting every git memory.

### #8 Remote Agent Session Steering

Query:

```text
怎么远程给一个正在运行的长驻 agent 会话注入指令
```

Expected:

```text
agentbridge_remote_session_steer_gap_20260529
```

FTS and hybrid choose adjacent remote-session handoff and setup memories, but
semantic ranks the expected decision at #2. This is the cleanest evidence that a
bounded semantic rescue path can help when lexical retrieval misses an older
decision.

However, the same run shows semantic saturation elsewhere: #2/#5/#9/#14 all
return unrelated high-cosine candidates. A semantic rescue should therefore be
tested as a narrow acceptance gate with negative controls, not as an unrestricted
blend into production ranking.

### #9 Agent-Bridge North Star

Query:

```text
agent-bridge 这个项目的核心愿景定位是什么
```

Expected:

```text
agent_bridge_northstar_bidirectional_bridge_20260529
```

The expected memory is the real North-Star answer: Agent-Bridge exists as a
bidirectional bridge between human-facing workflows and agent-native operations.
Current FTS/hybrid results prefer newer implementation and surface memories such
as LSWR, GoS-lite, Palace, setup, and skills routing. Semantic again returns
unrelated high-cosine memories.

This is a bad miss for continuity because the user is asking for durable project
identity, not a recent implementation detail. The likely fix is not generic
ranking pressure. It needs a curated core-vision alias or a dashboard/U anchor
that makes project North-Star memories first-class recall targets.

### #14 BioCortex Shadow Trial Contract

Query:

```text
biocortex 影子试验是只读的吗,会不会改默认检索顺序
```

Expected:

```text
ab_memory_continuity_t5_biocortex_shadow_trial_20260619
```

The expected memory states the T5 shadow-trial contract: it is read-only,
`used_for_return_order=false`, and does not change `memory_search` ordering.
FTS and hybrid find many BioCortex and T5/T6-adjacent memories, including newer
diagnostics and evidence batches, but not the specific T5 contract memory.

This is a specificity problem inside a dense same-domain cluster. Recency and
broad BioCortex vocabulary are not enough; the retriever must preserve contract
phrases like `read-only`, `return order`, `T5`, and `shadow trial` when the user
asks an operational safety question.

## Read

The remaining hard misses should not be attacked with one broad runtime change.
The next safe progression is to pick one target class and keep the gate
measurable:

1. Start with #2 because it is in the original #3897 target set and currently
   looks like a direct candidate-visibility miss.
2. Run an eval-only tool-surface alias/projection probe against #2 plus negative
   controls before touching production `memory_search`.
3. Treat #8 as a later semantic-rescue control case, because it proves semantic
   can help in one place but also proves that unrestricted semantic blending is
   unsafe on this corpus.
4. Handle #9 and #14 as curated-anchor and specificity problems rather than
   expecting tokenizer changes to fix them.

## Boundary

This report makes no runtime change and does not authorize search-order changes,
candidate-set expansion, graph priors, semantic blending, MCP surface changes,
memory writes, or deploy behavior.

The recommended next slice is:

```text
main-recall-case2-tool-surface-projection-probe-v1
```

That slice should remain eval-only and should falsify itself if it recovers #2
only by admitting broad unrelated tool/project memories into top 10.
