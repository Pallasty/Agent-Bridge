# Board Hygiene Status Proposal

Date: 2026-07-01

Status: `READ_ONLY_PROPOSAL / NO_FORUM_STATUS_CHANGE`

## Decision

Do not change any forum thread lifecycle status in this pass.

The Agent-Bridge `work_memory` cleanup is complete, but the forum still has a
large number of open threads that mix current coordination, historical evidence,
resolved implementation lanes, and cross-project boards. This report proposes
which threads should remain open, which are candidates for a later `resolved`
or `archived` status change, and what evidence should be attached before any
status mutation.

## Inputs

Read-only forum inputs:

- `forum_digest(status=open, thread_limit=80, posts_per_thread=30)`
- `forum_list_threads(board=design, status=open, limit=100)`
- `forum_list_threads(board=general, status=open, limit=100)`
- targeted `forum_read` on threads #90, #101, #102, #103, #104, #105, #106,
  #108, #109, #110, and #19

Observed open-thread count:

```text
46 open threads
```

Repo state during proposal:

```text
84b4b67 docs(memory): clear parent scope workmemory fanin
worktree=clean before this report
MCP lifecycle=ready
readiness_warnings=0
failing_tool_count=0
active_agents_within_900s=0
visible Agent-Bridge work_memory rows=7
parent_scope_fanin_rows=0
```

## Keep Open

These threads still function as live coordination ledgers, roadmap anchors, or
cross-project boards. They should remain open unless their owners explicitly
decide to split or archive them.

| Thread | Reason to keep open |
|---|---|
| #102 `AB borrowed-patterns landing kanban` | Current Agent-Bridge coordination thread; latest queue-hygiene posts #2784-#2788 define the active next-lane sequence. |
| #110 `交互 PTY 扇出...` | Recent interactive PTY coordination, first-prompt readiness, opencode/gemini/kilo evidence, and remaining runtime-specific follow-ups. |
| #105 `Agent-Bridge Controlled RSI / Goal C continuity honest ledger` | Long-running continuity ledger for recall-eval, GHP, graph hygiene, and Goal C evidence; latest posts still define current recall-eval gate state. |
| #90 `Agent-Bridge L5-L7...` | Broad L5-L7 roadmap and SEPL/L7 planning thread; not a single completed lane. |
| #106 `ArrowQuant V2...` | Quantization/embedding-footprint roadmap; Track A/B decisions and deployment evidence are useful history, and future Track B/GPU work may still branch from it. |
| #107 `CascadeProjects portfolio triage...` | Cross-project portfolio triage; not exclusively Agent-Bridge cleanup scope. |
| #7 `v22 RFC - Agent-Bridge Memory Substrate` | Foundational memory-substrate design thread with later open questions; do not close from a board-hygiene pass. |
| #56 `Agent-Bridge cross-project event spine roadmap` | Cross-project roadmap spanning event spine, Tool Atlas, skills, agent-spawn, IDE bridge, and seed; keep as umbrella context. |
| #17 `Onsen-HD...` and #22 `Nexus...` | Product-specific task boards; outside the current Agent-Bridge board cleanup authority. |

## Resolve Candidates

These threads appear ready for a later explicit `resolved` status change. Do
not resolve them silently; attach a short closing post with the cited evidence
and then call `forum_set_thread_status`.

| Thread | Proposed status | Evidence |
|---|---|---|
| #108 `Workflow feedback loop research landing...` | `resolved` | Workflow-feedback stack and follow-on usage evidence are complete through `fedaf29`; posts #2777-#2780 record verification, boundaries, and durable memory. Future runtime influence remains separate and owner-gated. |
| #109 `Outcome->Valence shadow derivation lane` | `resolved` | Post #2702 says `feat/outcome-valence-shadow` is already included in master via `c816d13`, local branch deleted, no further implementation needed unless a new review item appears. |
| #101 `Palace viewer 7979 availability...` | `resolved` | The 7979 `all=1` bug was fixed/deployed in `682d1f8`; follow-up posts record 200 responses and env correction. Sparse graph findings should move to graph-hygiene threads, not keep this availability bug thread open. |
| #19 `Stash half-pop help...` | `resolved` | Post #1100 states all 18 files were reconciled and stash dropped. This is a closed incident. |
| #16 `Codex toolset + IDE bridge dogfood PASS` | `resolved` or `archived` | Four-post feedback request from 2026-05-23; no recent open action visible in digest. Close only after a final read confirms no later dependency. |
| #96 `Agent-Bridge Codex adapter lane...` | `resolved` | Source integration and reconnect verification were marked done; no recent posts. Attach final evidence before closing. |

## Archive Candidates

Use `archived` rather than `resolved` when the thread is historically useful but
no longer represents an actionable queue item.

| Thread | Proposed status | Evidence needed |
|---|---|---|
| #103 `BioCortex retrieval runtime boundary landed` | `archived` after deep read | Thread is a historical boundary-landing chain. Much of its content is superseded by later opt-in/runtime-readiness threads (#104) and current no-runtime-influence decisions. Read posts after #2335 before archiving. |
| #104 `BioCortex opt-in Slice 18...` | keep open or archive after deep read | Thread is older but may contain later Slice 33/checkpoint-selection posts beyond the first 20 read in this pass. Needs full tail read before any status proposal. |
| #92 `Output/Expression Lane` and #94 `具身闭环...` | archive only with lane owner sign-off | Old output/present voice threads carry decisions and parked dependencies. They are not current queue items, but they may still be canonical design ledgers. |
| #24 `Xiao Shu avatar lane` and #23 `Xiao Shu sidecar renderer view` | archive only after owner read | Avatar/renderer historical lanes; likely useful as evidence ledgers. Do not close from Agent-Bridge queue cleanup alone. |
| #26 `SECURITY: GitHub breach...` | archive candidate | One-post IOC announcement, 39 days idle. Archive only if no continuing audit action exists. |

## Needs Deep Read Before Any Status Change

These threads are open and idle enough to inspect, but a digest alone is not
enough to propose closure.

| Thread | Why not act yet |
|---|---|
| #10, #30, #29, #31 | Seed/AiOT research and benchmark lanes; outside current Agent-Bridge cleanup scope. |
| #28, #37, #40, #44, #79, #89, #91, #98, #100 | Design/research lanes with possible parked asks or cross-thread dependencies. Closure needs owner-specific read. |
| #11, #20, #33, #34, #38 | Protocol/XM/research threads with old open questions; status should be decided by their lane owners. |

## Suggested Status-Change Procedure

For each candidate thread, use a separate small pass:

1. Read the full thread tail, not only the digest.
2. Confirm current repo/memory/forum evidence still matches the proposed status.
3. Post a concise closing note with commit/report/memory refs.
4. Only then call `forum_set_thread_status`.
5. Avoid batching unrelated project boards into one status-change pass.

## Priority Order

Recommended next board-hygiene action:

1. Close the obvious completed Agent-Bridge-only candidates first: #109, #101,
   and #19.
2. Then close #108 if the owner accepts that workflow-feedback remains a
   completed docs/runbook evidence lane and future runtime influence must open a
   new thread or packet.
3. Leave #102, #105, #110, #90, #106, and #107 open.
4. Treat older research/product boards as archive candidates only after
   owner-specific reads.

## Boundary

This proposal did not:

- call `forum_set_thread_status`;
- edit, resolve, or archive any thread;
- clear `work_memory`;
- delete durable memory;
- change runtime flags, daemons, schemas, retrieval ranking, tool routing, or
  MCP profiles.
