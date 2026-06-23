# Main Recall Case #8 Remote-Session Eval Assembler

Date: 2026-06-23
Host: `aio2`
Worktree: `/Data/CascadeProjects/agent-bridge`
Base: `97364e1` (`test(memory): add trigger runtime audit probe`)
Scope: eval-only; no runtime implementation

## Why

The case #2 production review packet moved the next recommended gate to
`main-recall-second-hard-family-eval-v1`: pick another pinned hard miss,
preferably #1 or #8, and build an eval-only projection/role assembler with clean
controls before any runtime flag is designed.

This slice chooses #8 because it is a different failure family from #2:

```text
怎么远程给一个正在运行的长驻 agent 会话注入指令
```

Expected key:

```text
agentbridge_remote_session_steer_gap_20260529
```

#8 is not a zero-row CJK miss. Baseline FTS returns rows, but adjacent
remote/session/handoff memories outrank the original steering-gap decision. The
new assembler therefore tests a narrow role-aware projection family rather than
a broad semantic blend.

## What Changed

`crates/bridge/examples/recall_eval.rs` now has an eval-only remote-session
steering projection path:

- builds a read-only in-memory FTS table from `COALESCE(fts_content, content)`;
- adds canonical projection tokens only inside that scratch table;
- accepts candidates with at least four shared remote-session projection terms;
- strict mode requires `projremotesession` plus steering/session anchors;
- removes `work_memory_*`, snapshot, alert, and skill rows from durable mode;
- labels candidates as `primary`, `delivered-capability`,
  `adjacent-handoff`, `diagnostic-meta`, or `other`;
- excludes diagnostic/meta candidates unless the query asks for that domain;
- sorts by role, then overlap, then key for deterministic output;
- prints #8 negative and positive controls.

This is not connected to `SqliteStore::memory_search`, MCP `memory_search`,
schema, tokenizer, graph expansion, semantic search, or live ranking.

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

This is useful smoke evidence, but it is not the canonical frozen Mac snapshot.
The pinned 3022-row `multilingual-e5-small` snapshot should still be replayed
before this gate is treated as production-grade evidence.

## Case #8 Result

Before role-aware sorting, the target is present but buried:

```text
remoteproj hit: 9
remoteproj_acc hit: 9
remoteproj_acc_durable hit: 8
remoteproj_strict hit: 8
role_aware hit: 1
```

Strict durable top before role-aware sorting:

```text
1. agent_bridge_steer_presence_stale_mux_20260531
2. output_lane_e1_shipped_thread92_20260529
3. agent_spawn_kilo_retry_on_miss_and_shared_checkout_churn_20260531
4. kilo_codex_dual_executor_live_verified_20260531
5. session_handoff_agent_spawn_remote_steer_retry_to_aio2_20260531
6. mac_next_round_tasks_20260603
7. session_handoff_c3_compact_tombstone_curation_to_aio2_20260602
8. agentbridge_remote_session_steer_gap_20260529 <== EXPECTED
```

Role-aware strict durable top:

```text
1. role=primary agentbridge_remote_session_steer_gap_20260529 <== EXPECTED
2. role=delivered-capability agent_bridge_steer_presence_stale_mux_20260531
3. role=adjacent-handoff agent_spawn_kilo_retry_on_miss_and_shared_checkout_churn_20260531
4. role=adjacent-handoff agent_spawn_remote_ssh_and_steer_status_shipped_20260531
5. role=adjacent-handoff session_handoff_agent_spawn_remote_steer_retry_to_aio2_20260531
```

Accepted projection initially includes one `work_memory_*` row, but durable mode
removes it:

```text
accepted_work_memory=1 durable_work_memory=0
```

## Controls

Negative controls stayed clean:

```text
controls=6 nonempty_accepted=0 false_target_hits=0 work_memory_hits=0
```

The negative controls cover plain SSH access, git remote vocabulary, generic
agent-session summarization, process signals, remote database migration, and
retrieval-quality tuning.

Positive controls stayed healthy:

```text
controls=6 durable_hits=6 strict_hits=6 strict_chain_hits=6 strict_empty=0 role_aware_hits=6 role_aware_rank1_hits=6
```

The positive controls cover Chinese and English paraphrases for long-running
remote agent sessions, `agent_steer_drive`, tmux/send-keys, AB session handles,
and the original remote-steering gap wording.

## Hard-Tier Read

The standing aggregate remains unchanged because the assembler is not wired into
any production or aggregate retrieval mode. On this drift-prone Aio2 live store:

```text
hard-tier R@10: fts=0.125 fts+graph=0.125 hybrid=0.125 semantic=0.000
hard fts misses: #1, #2, #4, #7, #8, #9, #14
hard zero-row fts misses: #1, #2
```

Those live numbers should not replace the canonical Mac snapshot anchor from
the case #2 production packet.

## Decision

The second hard-family eval gate has useful evidence:

- case #8 role-aware rank improves from strict durable rank 8 to rank 1;
- negative controls are clean;
- positive controls all recover the expected target at role-aware rank 1;
- candidate contamination is removed by durable filtering;
- no runtime retrieval path changed.

This is still a production NO-GO for default `memory_search`. The result argues
for continuing the eval ladder, not for wiring remote-session projection into
the store. Required next gates remain:

1. replay #8 on the pinned Mac snapshot;
2. add a named eval aggregate row that includes role-aware case #2 and #8;
3. harden read-only snapshot opening before more pinned comparisons;
4. only then design an explicit opt-in flag or cohort boundary.
