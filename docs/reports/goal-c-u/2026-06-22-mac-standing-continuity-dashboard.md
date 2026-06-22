# Goal C U Report - Mac Standing Continuity Dashboard

Date: 2026-06-22

Host: macOS `maxiaodeMac-Pro.local`

Verdict: `actionable` for report review and trigger-aware recall evaluation only.

This is the first Mac Goal C `U` refresh after the standing store-side
continuity dashboard shipped as `agent-bridge continuity-report`. It is
report-first and read-only. It does not add an MCP tool, mutate runtime state,
change retrieval order, write memory, approve graph/PageRank influence, or
authorize an executor.

## Source Anchors

| Anchor | Value |
|---|---|
| repo worktree | `/Users/pallasting/Projects/agent-bridge` |
| source commit | `accdddce39ff360c573da314ae522b63e7e07317` |
| source subject | `feat(cli): agent-bridge continuity-report subcommand + continuity module` |
| deployed binary | `/Users/pallasting/.local/bin/agent-bridge.real` |
| deployed sha256 | `947facd5023113959ec0ff6d8f943b643c42a179c8765a9ed45ef91022233b7e` |
| deployed version | `ab-bridge 0.1.0` |
| report timestamp | `2026-06-22T09:51:08Z` |
| active Codex profile | `codex` desktop, `gpt-5.5`, `xhigh`, `essential`, `codex-lean` |

## Board Window

Thread #120 is the controlling Goal C board thread.

Current direction consumed:

- #3838 reports that the store-side standing continuity dashboard is shipped:
  CLI plus on-demand `continuity` skill, zero new MCP schema surface.
- #3838 keeps the contract from #3736/#3774/#3833: FTS R@10 is the headline
  continuity number; embedding-space health explains semantic weakness but is
  not itself proof of continuity improvement.
- #3833 says trigger-to-FTS projection is mechanically live but not yet proven
  by the current `recall_eval` corpus because the 18 gold keys do not overlap
  the retrieval-trigger cohort.
- #3826 says Goal B pressure is now mostly incremental tool growth from gate
  families, not blind deletion of cold tools.
- #3837 keeps BioCortex S132 static/manual-review-only, with no runtime
  authority or lift claim.

This report follows that direction: refresh `U`, name one external next
evaluation, and do not add a tool or executor.

## Runtime And Lifecycle

Fresh local `doctor` on the deployed binary reported:

- `6 ok / 3 warn / 0 fail`;
- wrapper and real binary present;
- daemon PID `2259` running with `AB_SUBSTRATE_PROJECTION=svd`;
- at least one current `.real` MCP server active;
- 5 current `.real` MCP servers and 5 stale `.real` MCP servers observed;
- stale processes belong to older Claude, Cursor, and one older Codex app-server
  session; this current Codex session is already on a current `.real`;
- remaining warnings are missing `/Users/pallasting/.local/bin/ab-system-control`
  desktop helper checks, not Agent-Bridge MCP readiness failures.

`mcp_lifecycle_digest` reported:

- lifecycle state: `ready`;
- readiness state: `ready`, warnings `0`;
- daemon HTTP `http://127.0.0.1:7878/healthz`: `ok`;
- Palace `http://127.0.0.1:7979/healthz`: `ok`;
- Palace graph observed;
- current Codex exposed tools: `40`;
- scoped failing tool count: `0`.

## Event Spine

`event_spine_snapshot(window_secs=3600, limit=500, include_events=false)`
reported:

- candidate count: `44`;
- event count: `44`;
- truncated count: `0`;
- sources: `43` MCP tool calls, `1` MCP tool error;
- hash chain verified: `true`;
- chain head:
  `ec041679a63c7ff071ff9b81a3cd453ca5e6d090470bf2268eb9814a5b347411`.

This supports replayability for the report window. It does not prove continuity
improvement.

## Standing Continuity Dashboard

Command:

```bash
/Users/pallasting/.local/bin/agent-bridge.real continuity-report --json
```

Output summary:

| Metric | Value |
|---|---:|
| active memories | 2995 |
| embedded active memories | 2995 |
| dominant backend | `multilingual-e5-small` |
| dominant backend vectors | 1624 |
| anisotropy ratio | 0.906 |
| stale vectors | 1371 |
| stale fraction | 0.458 |

Embedding backend mix:

| backend | vectors |
|---|---:|
| `multilingual-e5-small` | 1624 |
| `<null pre-v26>` | 1324 |
| `all-MiniLM-L6-v2` | 45 |
| `fnv1a-hash-384` | 2 |

Read:

- Mac e5 geometry is severely anisotropic. Cosine semantic ranking is not a
  trustworthy primary continuity signal on this host.
- The 45.8% stale-vector fraction is a hygiene signal. It should not be framed
  as a recall lever unless a before/after `recall_eval` delta proves it.
- The store-side dashboard is now standing and cheap to refresh, but it only
  supplies the embedding-space half of `U`.

## Recall Anchor

Command:

```bash
cargo run -p ab-bridge --example recall_eval
```

The harness auto-selected `AGENT_BRIDGE_ONNX_MODEL=e5-small` from the store's
dominant `embedding_backend` and confirmed a real model before measuring
semantic recall.

Per-mode recall over the fixed 18-case held-out corpus:

| mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| fts | 0.278 | 0.500 | 0.667 | 0.378 |
| hybrid | 0.111 | 0.500 | 0.500 | 0.228 |
| semantic e5 | 0.000 | 0.111 | 0.111 | 0.039 |

Per-tier read:

| mode/tier | n | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|---:|
| fts/easy | 2 | 0.000 | 0.500 | 0.500 | 0.125 |
| fts/moderate | 8 | 0.625 | 0.875 | 1.000 | 0.745 |
| fts/hard | 8 | 0.000 | 0.125 | 0.375 | 0.075 |
| hybrid/hard | 8 | 0.000 | 0.000 | 0.000 | 0.000 |
| semantic/hard | 8 | 0.000 | 0.125 | 0.125 | 0.062 |

Offline FTS plus direct graph-neighbor candidate expansion:

| mode | n | hit | added | rate | MRR | avg candidates | neighbor rows |
|---|---:|---:|---:|---:|---:|---:|---:|
| fts+graph | 18 | 0.667 | 0 | 0.000 | 0.378 | 34.11 | 773 |

Read:

- FTS remains the headline continuity baseline on this Mac store.
- The true gap is hard-tier cross-vocabulary recall: FTS hard R@10 is only
  `0.375`, and hybrid hard is `0.000`.
- Semantic e5 is not the answer today; overall semantic R@10 is `0.111`.
- Direct graph-neighbor append did not recover any additional FTS misses in this
  run. It remains review evidence, not live ranking authority.

## Tool Surface And Dispatch

`tool_atlas_snapshot` and `mcp_dispatch_audit` for this Codex Desktop profile
reported:

- current exposed tools: `40`;
- observed tools in the one-hour window: `10`;
- cold tools: `32`;
- failing tools: `0`;
- optimization candidates: none;
- one observed `work_memory` validation error from an invalid `get` call without
  a key; classified as expected input validation;
- hot usage is dominated by board/lifecycle/reporting reads in this report run.

Read:

- The Codex lean surface is currently stable and not failing.
- The right Goal B move is still to block unnecessary new gate tools before they
  enter the default surface, not to remove cold collaboration/session tools from
  one short report window.

## Skill Loader Note

The `continuity` skill exists at:

```text
/Users/pallasting/.codex/skills/continuity/SKILL.md
```

This Codex session's skill list was generated before that file was created, so
the skill is not visible in the current prompt's declared skill list. A full
Codex restart should make it auto-discoverable. MCP reconnect alone does not
refresh Codex skill metadata. The current run manually read and followed the
skill.

## Proposed Actions

| Action | Owner | Anchor | Falsifier | Rollback | Next decision |
|---|---|---|---|---|---|
| Add a trigger-aware recall eval corpus for rows with `continuity_retrieval_trigger` | memory-continuity lane | #3833 plus `recall_eval` hard-tier contract | Trigger projection does not improve hard-tier R@k on its own cohort | Revert docs/test/example commit; no runtime state touched | If lift exists, decide whether trigger projection needs a guarded production path |
| Keep semantic whitening/reindex as diagnostic/hygiene, not main continuity lever | memory-continuity lane | anisotropy 0.906, semantic R@10 0.111, stale fraction 0.458 | A larger held-out eval shows semantic or reindex produces reliable hard-tier lift | Revert any proposed ranking/reindex plan before live mutation | Only run as read-only probe or separately approved hygiene task |
| Keep Codex tool surface unchanged for now | Codex integration lane | 40 tools, 0 failing, no optimization candidates | Repeat windows show failing/cold gate tools with concrete errors | Revert profile allowlist edit if made | Watch next audit after more normal work, not during report-heavy traffic |

## Non-Authorizations

This report does not authorize:

- runtime candidate-set expansion;
- production search-order changes;
- semantic whitening in live ranking;
- graph-neighbor or PageRank ranking influence;
- memory reindex writes;
- graph edge writes;
- new MCP tools;
- an approval-gated executor;
- automatic branch, commit, push, deploy, memory write, or SEPL write behavior.

## Decision

The standing dashboard is now usable on Mac. The first adopted action should not
be another gate or executor. It should be a trigger-aware, held-out recall
evaluation that tests whether `continuity_retrieval_trigger` projection improves
the exact hard-tier gap that `recall_eval` exposes.

Rollback for this document:

```bash
git revert <commit-that-adds-this-report>
```

No runtime restart is required for the document itself.
