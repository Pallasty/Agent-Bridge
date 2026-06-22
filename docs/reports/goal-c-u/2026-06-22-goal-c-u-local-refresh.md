# Goal C U Local Refresh

Date: 2026-06-22
Surface: Codex Desktop / GPT-5.5 / xhigh / `essential` + `codex-lean`
Thread: #120, claim #3909
Scope: report-only, no runtime mutation

This run refreshes the standing Goal C `U` surface after the main
`recall_eval` hard-tier anchor and CJK empty-fallback probe landed. It is a
report artifact only. It does not add an MCP tool, does not start an executor,
does not change retrieval, and does not authorize production runtime behavior.

## Source State

Git state at the start of the run:

- local `master`: `1afb604`
- GitLab `origin/master`: `1afb604`
- GitHub `github/master`: `1afb604`
- worktree: clean

During pre-commit verification, GitHub advanced to `7ee0039`
(`test(memory): expand trigger policy gate controls`). The local checkout was
fast-forwarded before committing this report. That change touched
`trigger_recall_eval` and GHP/report files, not this report or main
`recall_eval`.

Board state:

- #120 had no posts after #3907 before this run.
- #3909 claimed this report-only refresh.
- Goal C controlled-RSI plan is already closed at 5/5.
- The standing decision remains: report first, no new `U` MCP tool, no
  executor, no automatic self-patching.

## Recall Anchor

Command:

```sh
cargo run -p ab-bridge --example recall_eval
```

Host/model:

- store: `/Users/pallasting/Library/Application Support/agent-bridge/state.db`
- auto-selected `AGENT_BRIDGE_ONNX_MODEL=e5-small`
- embedding backend: `multilingual-e5-small`
- semantic: enabled, real model confirmed

Overall metrics:

| mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| fts | 0.278 | 0.556 | 0.611 | 0.361 |
| hybrid | 0.111 | 0.444 | 0.500 | 0.235 |
| semantic | 0.000 | 0.111 | 0.111 | 0.056 |

Hard-tier production anchor:

| mode | R@10 |
|---|---:|
| fts | 0.250 |
| fts+graph | 0.250 |
| hybrid | 0.000 |
| semantic | 0.125 |

Candidate probe:

| probe | overall R@10 | hard R@10 | added hits over FTS misses |
|---|---:|---:|---|
| fts+cjk | 0.667 | 0.250 | #1, #17 |
| fts+cjk_acc | 0.167 | 0.125 | #1, #17 |
| fts_empty+cjk | 0.667 | 0.375 | #1 |

Current hard misses after the probe:

- #2: zero FTS rows and not recovered by CJK accepted fallback
- #5: FTS returns rows, but not the expected memory
- #8: expected key remains buried outside current production modes
- #9: core Agent-Bridge vision query remains missed
- #14: BioCortex shadow/readonly query remains missed

Read: the CJK empty-fallback probe moved the main hard-tier anchor by one case
(#1). That is useful evidence, but still not enough for production retrieval
authority. The next continuity-relevant question is why #2 stays invisible even
though it is another zero-row Chinese hard miss.

## Tool Surface

Two-hour scoped Tool Atlas:

| field | value |
|---|---:|
| current tools | 40 |
| observed tools | 14 |
| hot tools | 5 |
| cold tools | 26 |
| failing tools | 1 |

The one scoped failing tool is `changes_digest`, but a live probe after the
fix returned structured JSON rather than a backend error:

```text
merge_base_found=false
branch_range=null
warnings=["branch_vs_main: could not resolve merge-base with main/master; diff omitted"]
```

Classification: `telemetry_window_residue`. It should be watched until the
error window ages out, but it is not the next adopted action.

Seven-day wider Tool Atlas still shows historical `memory_save` errors:

```text
invalid continuity.continuity_role: 'decision'
allowed: state, constraint, procedure, evidence, preference, warning, archive
```

Classification: `ergonomics_candidate`, not the current first action. It is
worth fixing or documenting if it repeats in the scoped current-model window.

## Lifecycle And Runtime

`mcp_lifecycle_digest` with local install and runtime health checks reports:

- readiness: `ready`
- readiness warnings: `0`
- daemon-http health: `ok` at 7878
- Palace health: `ok` at 7979
- Palace graph observed: yes
- MCP profile: Codex Desktop / GPT-5.5 / xhigh / `essential`
- toolset: `codex-lean`

Palace memory-region stats:

| field | value |
|---|---:|
| nodes | 710 |
| edges | 284 |
| orphan nodes | 512 |
| connected ratio | 0.279 |
| explicit edges | 255 |
| coactivation edges | 29 |
| stale nodes | 0 |

Read: runtime is healthy, but the graph still has a weak connected ratio. That
is a continuity-dashboard pressure signal, not an immediate reason to change
retrieval ranking.

## Replayability

`event_spine_snapshot(window_secs=7200, limit=80)` reports:

- candidate rows: 83
- included events: 80
- sources: 77 MCP tool calls, 3 MCP tool errors
- chain verified: true
- chain head:
  `82f362b7535824a0b0c9e0aecb835b71cd87b5c46e187408d685a23d83677ae9`

This is enough for replayability of the report inputs. It is not itself a
continuity improvement.

## Work Memory

Current active work memory says the CJK empty-fallback probe is complete:

- main/origin/github at `1afb604`
- `recall_eval` tests: 6 passed
- `trigger_recall_eval` tests: 18 passed
- `cargo check`: passed
- hard probe R@10: `0.250 -> 0.375` via #1 only

## Action Candidates

| Candidate | Owner | Anchor | Falsifier | Next gate |
|---|---|---|---|---|
| Diagnose main recall #2 zero-row miss | current Goal C recall lane | #2 has zero FTS rows and is not recovered by accepted CJK fallback | diagnostic shows #2 lacks recoverable lexical/CJK evidence or only recovers by oracle-only text | eval/report-only probe |
| Track `changes_digest` error aging | tool-surface lane | two-hour audit still shows old merge-base errors | new live calls still return backend errors after reconnect | no code unless fresh failure appears |
| Improve `memory_save` role ergonomics | tool-surface lane | seven-day Codex desktop data has `continuity_role='decision'` validation errors | scoped current-model window stays clean and no caller repeats the mistake | docs/schema alias or clearer error, no new tool |
| Graph connectivity hygiene refresh | memory-continuity lane | Palace connected ratio is 0.279 and orphan nodes are 512/710 | safe scoped link candidates are absent or speculative | report-only inventory before write |

## Adopted Action

Adopted action for the next slice:

> Run an eval/report-only diagnostic for main `recall_eval` hard case #2.

Why this one:

- it is directly tied to the #3897 hard-tier continuity gate;
- it targets a zero-row Chinese hard miss that CJK accepted fallback did not
  solve;
- it can be done without touching production retrieval;
- it will tell whether the CJK fallback idea has a tractable next step or
  whether #2 requires a different lever.

Expected output:

- a new report under `docs/reports/goal-c-u/`;
- optional diagnostic-only additions to `crates/bridge/examples/recall_eval.rs`
  if the current output is insufficient;
- no production `memory_search`, tokenizer/schema/reindex, ranking, graph,
  semantic, MCP, or memory-write change.

Acceptance:

- explain why #2 has zero FTS rows;
- explain why `fts+cjk` and `fts+cjk_acc` miss #2;
- classify whether #2 is recoverable by CJK text visibility, synonym/semantic
  intent, graph neighborhood, stale/absent expected content, or corpus-design
  issue;
- preserve current #1 recovery and hard-tier anchor reporting.

Rollback:

- if this report is wrong, revert the commit that adds it;
- if any diagnostic code is added later, it must be example-only and removable
  without changing live retrieval behavior.
