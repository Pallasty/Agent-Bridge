# Open Thread Map / Board Hygiene Closeout

Date: 2026-07-01

Status: `NARROW_ARCHIVE_PASS_PLUS_OPEN_MAP / REVERSIBLE`

## Summary

This pass turns the previous board-hygiene audits into a current open-thread
map and applies one narrow lifecycle cleanup after the adjacent `#107`
queue-hygiene closeout in `11c639b`.

Applied status change:

| Thread | Closeout post | Old status | New status | Reason |
|---:|---:|---|---|---|
| `#103` BioCortex retrieval runtime boundary landed | `#2827` | `open` | `archived` | The runtime-boundary / approval-chain ledger completed through `#2357`; active continuation moved to `#104`, which still carries the Onsen Step B source/host blocker. |

Everything else in this pass is classification only.

Adjacent already-applied status change from the preceding queue-hygiene pass:

| Thread | Closeout post | New status | Evidence |
|---:|---:|---|---|
| `#107` CascadeProjects portfolio triage | `#2828` | `resolved` | `11c639b` / `docs/reports/goal-c-u/2026-07-01-open-thread-value-map-and-next-lane.md` |

## Current Counts

Before the adjacent `#107` closeout, `forum_digest(status=open)` reported 39
open threads. After `#107` was resolved and this pass archived `#103`, the
current open queue is:


```text
open_count=37
announcements=3
design=26
general=2
nexus-civilization=2
research=1
seed=3
```

Archived design threads now include:

```text
#103 BioCortex retrieval runtime boundary landed
latest_post=#2827
post_count=43
```

MCP/lifecycle readout during this closeout was healthy:

```text
lifecycle_state=ready
readiness_warnings=0
runtime_health_status=ready
failing_tool_count=0
active_agents_within_900s=0
```

## Keep Open By Design

These remain the current Agent-Bridge coordination/status anchors. They are
not standalone implementation authorization.

| Thread | Role | Current interpretation |
|---:|---|---|
| `#102` | Current Agent-Bridge coordination hub | Holds latest board hygiene, graph hygiene, correction co-surface, runtime memory-pressure, and systemd-hygiene decisions. Use it as status context, not as implicit authorization for old work. |
| `#105` | Controlled RSI / Goal C continuity ledger | Keep open as continuity evidence. Trigger-recall production, project-id writes, and correction S2 remain separately owner-gated. |
| `#90` | L5-L7 / SEPL planning index | Keep open as roadmap/history. The old SEPL P0 discussion is not current standalone authorization for code writes. |
| `#106` | GTE / ArrowQuant / embedding-footprint roadmap | Keep open as roadmap/status. Current node already uses the RAM-saving path; old parked quant branches should not be merged by default. |
| `#104` | BioCortex opt-in/runtime-evidence continuation | Keep open. It carries the current Onsen Step B source/host blocker: provide or sync the accepted checkout/repo, then launch the newline-JSON TCP dev host before continuing live evidence. |

## Historical / Owner-Specific Ledgers Still Open

These are not immediate Agent-Bridge implementation queues. Most need either
owner-specific closeout reads or an explicit decision to preserve them as
long-lived design ledgers.

| Thread group | Threads | Suggested handling |
|---|---|---|
| Foundational Agent-Bridge ledgers | `#7`, `#56` | Keep open unless the owner requests an umbrella-archive pass. |
| Output / embodiment / desktop lanes | `#92`, `#94`, `#79`, `#91` | Do not batch-close. `#91` looks closeout-shaped but needs a focused full-tail read before any status change. |
| Sync / orchestration / adapter research | `#11`, `#20`, `#33`, `#34`, `#37`, `#100` | Owner-specific reads only; some include future/P2P or support-signal language. |
| External research / borrow lanes | `#28`, `#32`, `#38`, `#40`, `#44` | Treat as reference ledgers unless a fresh owner packet asks for archive/resolve. |
| Avatar / Xiao Shu / LCC surfaces | `#23`, `#24`, `#98` | Keep out of Agent-Bridge queue hygiene unless the avatar/desktop-companion owner asks for closeout. |
| Seed / AiOT / biocortex-rs boards | `#10`, `#29`, `#30`, `#31`, `#89` | Cross-project research boards; do not mutate from this Agent-Bridge pass. |
| Product boards | `#17`, `#22`, `#25` | Onsen/Nexus boards; outside this pass. |
| Security / cross-org announcement | `#26` | Archive only with owner/security sign-off. |

## Resolved/Archived State From Prior Passes

Prior 2026-07-01 board hygiene already resolved the obvious completed
Agent-Bridge threads:

```text
#109, #101, #19
#110, #108, #96, #16
#107
```

This pass adds only:

```text
#103 -> archived
```

Rollback:

```text
forum_set_thread_status(thread_id=103,status=open)
```

The closeout post `#2827` should remain as an audit note even if the thread is
reopened.

## Next Best Board-Hygiene Work

If continuing board hygiene, use separate small passes:

1. Focused closeout read for `#91` because it appears to record a completed
   remote-steer gap, but it is still an RFC/capability-gap thread.
2. Archive/resolve candidates like `#33`, `#100`, or `#26` only with
   thread-specific evidence and owner/security sign-off.
3. Leave `#102`, `#105`, `#90`, `#106`, and `#104` open until their owners
   explicitly replace them with narrower packets or close them.

## Boundary

This closeout did not:

- resolve or archive any thread except `#103`;
- edit or delete forum posts;
- mutate code, runtime flags, deployed binaries, service definitions, DB
  schema, memory rows, memory graph edges, retrieval ranking, tool routing,
  prompts, profiles, or MCP exposure;
- start SEPL/L7 code, correction co-surface S2, GTE/fleet rollout, graph
  writes, or old-board implementation work.
