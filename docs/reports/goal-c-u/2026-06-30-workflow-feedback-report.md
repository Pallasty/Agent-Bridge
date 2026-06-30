# Workflow Feedback Report - 2026-06-30

Host: `pallasting-ThinkBook-14-G5-IRH`

Report timestamp: `2026-06-30T14:29:59Z`

Source branch: `feat/scope-survey-diagnostic`

Source commit: `b9f0091` (`docs: land workflow feedback loop research`)

Scope: report-first workflow-feedback maturity read; no runtime implementation

Verdict: `actionable`

## Technical Summary

Agent-Bridge has enough observability to start measuring workflow feedback as a
system, but not enough closed-loop evidence to let feedback automatically change
runtime policy, retrieval ranking, or tool exposure.

The current read is:

- Capture coverage is usable: memory/forum state, MCP telemetry, lifecycle
  digest, event-spine projection, and consolidation queues are all available.
- Attribution is partial: AB can connect some outcomes to tools, memories, and
  board decisions, but it does not yet have one normalized trajectory object
  linking goal, plan, tool spans, observations, outcome, reflection, and later
  retrieval.
- Feedback density is low: there are 615 active memory rows, but only 7 active
  dedicated `kind=feedback` rows. A broader tag search finds 24 feedback-labeled
  rows, still too sparse for automatic learning.
- Tool telemetry is dense enough for a first workflow report: the latest 7-day
  MCP window has 1320 calls, 10 errors, and 54 observed tools.
- Governance is the strongest axis: existing Goal C and AB patterns already
  prefer report-first, owner-gated, reversible changes.

The next slice should build an `Experience Object v0` fixture and a repeatable
read-only report generator. That should happen before any optimizer, RL path,
or default retrieval/tool-routing policy change.

## Source Anchors

| Anchor | Value |
|---|---|
| research design | `docs/design/WORKFLOW_FEEDBACK_LOOP_RESEARCH_2026_06_30.md` |
| research memory | `workflow_feedback_loop_research_20260630` |
| research forum | thread `#108`, posts `#2658`, `#2659` |
| report source commit | `b9f0091` |
| telemetry window | `2026-06-23T14:27:39Z` to `2026-06-30T14:27:39Z` |
| MCP lifecycle snapshot | `mcp_lifecycle_digest(window_secs=604800)` |
| tool telemetry | `mcp_dispatch_audit(window_days=7)` and `tool_atlas_snapshot(window_secs=604800)` |
| graph health | `memory_graph_topology(scope=project:/Data/CascadeProjects/agent-bridge, scope_mode=local_plus_global)` |
| consolidation state | `memory_consolidation_queue(scope=project:/Data/CascadeProjects/agent-bridge, scope_mode=local_plus_global)` |
| replayability | `event_spine_snapshot(window_secs=604800, limit=500, include_events=false)` |
| bottom-up counts | read-only SQLite queries against `/home/pallasting/.local/share/agent-bridge/state.db` |

This report does not mutate memory, write graph edges, change search order,
change MCP profiles, authorize an executor, or deploy code.

## Board And Coordination Read

The design board now has a dedicated thread for this lane:

| Thread | Read |
|---|---|
| `#108` Workflow feedback loop research landing | New lane anchor is live and has no open blocker. |
| `#105` Controlled RSI / Goal C | This report fits Goal C's report-first self-improvement boundary. |
| `#102` borrowed-patterns landing | Active adjacent work exists; this report should not consume implementation authority from those lanes. |

The board state supports continuing with a report/fixture slice. It does not
support silent runtime influence.

## Maturity Scorecard

| Axis | Score | Evidence | Interpretation |
|---|---:|---|---|
| Capture coverage | 3.5 / 5 | Lifecycle ready, event spine verified, 1320 MCP calls in 7 days, 2660 forum posts, 615 active memories. | Enough telemetry exists for a first standing report. Missing piece is one normalized workflow trajectory object. |
| Attribution quality | 2.5 / 5 | Tool calls include timing, size, source, model, profile, and host; memory graph has 1590 edges. | Useful for correlation and review, but causal grouping from goal to outcome is still mostly manual. |
| Feedback density | 1.5 / 5 | 7 dedicated active feedback memories; 24 broad feedback-tagged active rows. | Too sparse for calibrated learning. Feedback labels need to become routine. |
| Retrieval influence | 2.5 / 5 | `session_bootstrap` retrieved `workflow_feedback_loop_research_20260630` for a workflow-feedback query. | New lessons can enter bootstrap, but feedback still does not deliberately tune default retrieval. |
| Behavior lift | 1.5 / 5 | Tool telemetry and graph health exist, but no standing before/after workflow lift metric exists. | AB can observe work, not yet prove improved work-loop quality from feedback. |
| Governance | 4.0 / 5 | Goal C reports, owner gates, shadow-eval posture, and docs-first boundaries are established. | This is the strongest foundation; keep it intact while adding measurement. |

## Runtime And Lifecycle Evidence

`mcp_lifecycle_digest` reported:

| Axis | Value |
|---|---:|
| lifecycle state | `ready` |
| readiness status | `ready` |
| readiness warnings | `0` |
| current compact tool count | `97` |
| scoped failing tools | `0` |
| runtime health checked | `false` |

Read: the MCP surface is healthy enough for this report. Runtime HTTP/Palace
health was intentionally not checked because this slice only needs stdio,
memory, forum, and telemetry.

## Event Spine Replayability

`event_spine_snapshot` over the 7-day window reported:

| Metric | Value |
|---|---:|
| candidate events | 525 |
| included events | 500 |
| truncated events | 25 |
| tool-call events | 475 |
| tool-error events | 10 |
| agent-session events | 10 |
| semantic events | 5 |
| hash chain verified | `true` |

Chain head:

```text
cf980cbb40b71ad472961d33dc3082294537dcb618a501979b7f7d1287a28e07
```

Read: the event spine is enough to support an Experience Object fixture and
short-window replay. It is not yet a complete workflow episode store because
goals, plans, observations, decisions, and outcomes are not bound into one
record.

## Memory Substrate Evidence

Active memory state:

| Metric | Value |
|---|---:|
| active memories | 615 |
| active decisions | 411 |
| active lessons | 50 |
| active session handoffs | 49 |
| active work memories | 45 |
| active dedicated feedback rows | 7 |
| broad feedback-tagged active rows | 24 |

Graph state:

| Metric | Value |
|---|---:|
| total memory edges | 1590 |
| `evolved` edges | 1323 |
| `relates` edges | 141 |
| `supersedes` edges | 57 |
| `cofires` edges | 49 |
| coactivation pairs | 940 |
| total cofires | 1480 |

Scoped graph topology for project plus global memory:

| Metric | Value |
|---|---:|
| non-skill active denominator | 292 |
| orphan count | 14 |
| orphan fraction | 4.8% |
| P4 evolved coverage | 237 |
| P4 evolved fraction | 81.2% |
| top hub degree | 35 |
| top hub fraction | 12.0% |
| centrality readiness | `observe_then_bound_centrality_boost` |

Read: the graph is healthy enough for bounded shadow scoring. The low orphan
rate and high evolved coverage argue against emergency graph hygiene work. They
do not justify PageRank, centrality, or feedback-weighted ranking as a live
default.

## Consolidation Queue Evidence

`memory_consolidation_queue` for the same project scope reported:

| Bucket | Count |
|---|---:|
| scanned active records | 320 |
| handoff to decision | 10 |
| high-token low-use | 10 |
| duplicate lessons | 0 |
| stale warnings | 0 |
| harmful memories | 0 |
| too-large memories | 0 |
| gated actions | 0 |

Read: the queue is quiet on harmful/stale/duplicate feedback, which is good, but
that quietness should be interpreted cautiously because feedback density is low.
The most useful consolidation pressure is converting high-value handoffs into
durable decisions or lessons.

## Tool Telemetry Evidence

Seven-day MCP totals:

| Metric | Value |
|---|---:|
| total calls | 1320 |
| total errors | 10 |
| observed tools | 54 |
| current exposed tools | 97 |
| Tool Atlas cold tools | 62 |
| Tool Atlas failing tools | 4 |

By source:

| Source | Calls | Errors | Observed tools |
|---|---:|---:|---:|
| `claude` | 641 | 6 | 34 |
| `codex` | 615 | 4 | 36 |
| `manual` | 64 | 0 | 5 |

Hot tools:

| Tool | Calls | Errors | Avg ms | Avg result bytes | Read |
|---|---:|---:|---:|---:|---|
| `shell_exec` | 265 | 0 | 69809.1 | 1034.4 | Hot and slow because it includes long-running commands; optimize measurement, not necessarily the shell. |
| `memory_save` | 173 | 2 | 969.1 | 1255.3 | Hot and valuable; failure mode is schema misuse. |
| `forum_post` | 133 | 0 | 10.6 | 260.9 | Healthy coordination write path. |
| `plan_update` | 95 | 0 | 14.9 | 3450.1 | Healthy active-task planning path. |
| `work_memory` | 94 | 2 | 298.5 | 6890.9 | Healthy overall; errors are input-validation misses. |
| `forum_read` | 91 | 0 | 0.9 | 16084.7 | Healthy but can be payload-heavy. |
| `forum_digest` | 64 | 0 | 28.7 | 7949.5 | Healthy board-summary path. |
| `memory_get` | 54 | 0 | 57.0 | 2980.2 | Healthy targeted recall path. |
| `memory_search` | 42 | 0 | 124.3 | 29224.7 | Reliable but payload-heavy; compacting or result shaping is a good candidate. |

Recent error classes:

| Tool | 7-day errors | Interpreted cause |
|---|---:|---|
| `brave_web_search` | 3 | Missing `BRAVE_SEARCH_TOKEN`; environment/readiness issue. |
| `work_memory` | 2 | `get requires key`; usage/input issue. |
| `memory_save` | 2 | Invalid `continuity_role` values; schema usage issue. |
| `agent_kill` | 1 | Session already finished or unknown; stale target issue. |
| `github_pr_list` | 1 | Missing `GITHUB_TOKEN`; environment/readiness issue. |
| `plan_load` | 1 | Expected lookup miss for a missing plan key. |

Read: the core workflow tools are being used and mostly succeed. The main
quality opportunities are not more tools; they are compact payloads, better
schema affordances, and routine outcome labeling.

## Retrieval And Feedback Evidence

Memory query log:

| Metric | Value |
|---|---:|
| logged queries | 120 |
| average hit count | 3.78 |
| max hit count | 30 |
| average duration | 52.1 ms |

By query kind:

| Kind | Count | Avg hit count |
|---|---:|---:|
| `get` | 67 | 0.85 |
| `search_hybrid` | 31 | 8.71 |
| `search_fts` | 20 | 5.35 |
| `search_semantic` | 2 | 10.00 |

Bootstrap check:

- Query: workflow feedback loop research, experience object, report,
  self-improvement, tool telemetry learning.
- Result included `workflow_feedback_loop_research_20260630` in the state
  digest.

Read: retrieval can surface the new research memory when asked directly. That
is retrieval availability evidence, not behavior-lift evidence. To measure lift,
AB needs to record whether retrieved memories were used, stale, missing, or
harmful and whether later task outcomes improved.

## Methodology

This report combines:

1. MCP read-only snapshots for lifecycle, graph topology, consolidation,
   dispatch audit, Tool Atlas, forum digest, event spine, and bootstrap recall.
2. Read-only SQLite aggregation against the local AB state database.
3. Repo inspection for current branch, commit, and adjacent report conventions.

Claims are descriptive. They do not prove causality. Scores are heuristic
maturity ratings designed to guide the next implementation slice, not model
metrics.

## Limitations And Robustness Notes

- The 7-day MCP telemetry window is dense enough for a report, but not enough to
  prove behavior lift from feedback.
- Tool latency aggregates include long-running shell commands, so `shell_exec`
  p95 should not be interpreted as an MCP transport problem by itself.
- Feedback density is measured from stored memory rows and tags; missing labels
  can make stale/harmful/duplicate rates look cleaner than reality.
- The lifecycle digest's scoped telemetry showed zero observed tools for the
  current compact profile slice, while the all-source dispatch audit saw 1320
  calls. For this report, all-source telemetry is the better workflow evidence.
- No runtime HTTP/Palace health checks were run because the target question is
  workflow feedback, not daemon availability.

## Recommended Next Steps

### 1. Create Experience Object v0 fixture

Owner: next AB workflow-feedback lane.

Anchor: this report plus `WORKFLOW_FEEDBACK_LOOP_RESEARCH_2026_06_30.md`.

Action: create a small JSON fixture that binds one completed lane into:

```text
goal -> plan -> tool spans -> observations -> outcome -> reflection ->
retrieval trigger -> promotion decision
```

Falsifier: if existing telemetry cannot reconstruct a completed lane without
manual guesswork, the fixture must explicitly mark missing fields instead of
inventing them.

Rollback: remove the fixture/doc only; no runtime state depends on it.

### 2. Add a repeatable read-only report command or script

Owner: AB report-first lane.

Anchor: this Markdown report's metric set.

Action: make the aggregation repeatable so later sessions can compare capture
coverage, attribution quality, feedback density, retrieval influence, behavior
lift, and governance.

Falsifier: if repeated runs produce no adopted actions or no measurable trend,
keep it as an occasional manual report and do not add a new MCP surface.

Rollback: delete the script or leave it unexposed.

### 3. Increase low-friction feedback labels

Owner: memory-continuity lane.

Anchor: `memory_retrieval_feedback` already exists and is exposed.

Action: after important bootstraps/searches, label a few memories as `used`,
`stale`, `missing`, `harmful`, or `too_large` when the outcome is obvious.

Falsifier: if labels become noisy or ritualized, restrict them to explicit
review points and keep them out of ranking.

Rollback: feedback rows can remain inert; do not wire them into default
retrieval.

### 4. Reduce payload pressure for high-value read paths

Owner: tool-surface/report lane.

Anchor: `memory_search` average result size around 29.2k bytes and `forum_read`
around 16.1k bytes in this window.

Action: prefer compact digests, explicit limits, and report-shaped summaries
before adding new tools or broad reads.

Falsifier: if compacting hides needed evidence or increases follow-up calls,
keep full reads as the default for that workflow.

Rollback: usage convention only until measured; no runtime change required.

## Further Questions

- Which completed AB lane is the best first Experience Object fixture:
  `agent_send_input`, GTE-768 migration, or workflow-feedback research landing?
- Should feedback density be measured per session, per retrieval event, or per
  completed task outcome?
- What is the first behavior-lift metric that is honest and cheap: fewer tool
  errors, fewer repeated searches, faster post-restart recovery, or better
  handoff-to-decision conversion?
- Should the future repeatable report stay as a CLI/script first, or eventually
  become a read-only MCP tool after repeated manual use?
