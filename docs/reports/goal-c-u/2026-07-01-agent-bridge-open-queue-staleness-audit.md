# Agent-Bridge Open Queue Staleness Audit

Date: 2026-07-01

Status: `DOCS_ONLY_QUEUE_AUDIT / NO_RUNTIME_CHANGE / NO_DB_WRITE`

## Verdict

The current Agent-Bridge queue has no obvious non-gated implementation slice
that should be pushed immediately from the main worktree.

Several items that still appear in older board digests or work-memory snippets
are now stale because later reports, commits, or decision posts superseded
them. The remaining meaningful work is either owner-gated, maintenance-window
gated, or belongs in a dedicated conflict-resolution lane.

Current repo state during this audit:

- queue evidence includes `403db05` (`docs(memory): revalidate correction
  backfill preflight`) on top of the earlier `a03cc4d` preflight
- initial queue-audit commit was `b81b3fd`; later local follow-ups refreshed the
  baseline and incorporated the post-backfill verification state
- single worktree: `/Data/CascadeProjects/agent-bridge`
- working tree clean before this report
- MCP lifecycle: `ready`, readiness warnings `0`, failing tools `0`
- active `agent-bridge` presence within 15 minutes: `0` agents

This audit does not change runtime ranking, MCP profiles, environment flags,
schema, live memory DB contents, daemon state, or deployment.

## Stale Or Closed Queue Items

These should not be treated as active blockers anymore.

| Item | Current read | Closing evidence |
|---|---|---|
| PR #32 / `origin/claude/semantic-rebalance-20260630` pending merge or rebase | Stale. The branch tip is contained by `origin/master`; semantic rebalance landed through `ef5d05e`. | `6cf6563`, forum #102 post #2750, `2026-07-01-semantic-rebalance-branch-closure-audit.md` |
| Correction co-surface branch pending merge | Stale. PR #36 is merged on master; A1 write path and B1 gated read path are present. | `ed7f0cc`, forum #102 post #2749, `2026-07-01-correction-cosurface-link-review.md` |
| Centrality/PageRank prior as a candidate ranking lever | Closed as NO-GO. Centrality remains observability only, not ranking policy. | `230121f`, forum #102 post #2752, `2026-07-01-centrality-prior-offline-no-go.md` |
| Kilo/opencode interactive first-prompt readiness as an unverified fix | Closed for deterministic coverage. Kilo readiness-marker wait is verified locally; live provider tests remain explicitly opt-in. | `6066864`, forum #110 post #2753, `2026-07-01-kilo-first-prompt-readiness-verification.md` |
| Workflow-feedback stack as unfinished core plumbing | Closed through the low-risk promotion lane. Slices 1-10 are merged; remaining work is to use the runbook and gather lift/handoff evidence. | forum #108 posts #2690/#2693/#2696, `WORKFLOW_FEEDBACK_LOW_RISK_PROMOTION_RUNBOOK_2026_06_30.md` |
| Local GTE 768 runtime switch | Closed as no-op for this node. The live store is already schema v38 with active 768d `gte-multilingual-base` embeddings. | `2026-06-30-gte-768-local-runtime-switch-plan-closure.md` |
| BioCortex T6 side-signal head sample as runtime-influence evidence | Closed negative evidence. The redacted head sample showed `no_lift`; order movement alone is not relevance lift. | `52ee090`, forum #102 post #2751, `2026-07-01-biocortex-t6-relevance-lift-head-sample.md` |
| Correction co-surface single-edge backfill | Closed after the queue audit began. The live store now has 5 `corrects` edges and the single candidate edge exists with weight `1.4`. | `2026-07-01-correction-cosurface-single-edge-backfill.md`, read-only SQLite verification |
| Bounded coactivation latch | Stale as an active implementation gate. Current tree has the v38 bounded latch implemented and verified; live schema_meta is v39 and includes v38. | `2026-07-01-bounded-coactivation-latch-current-state.md`, `cargo test -p ab-store v38_` |

One older line inside `2026-07-01-correction-cosurface-link-review.md` still
says semantic rebalance should remain owner-reviewed before merge/deploy. That
was accurate when written, but is now superseded by the later semantic
rebalance closure audit and should be read as stale context, not as an active
queue item.

## Still Active But Gated

These are real follow-ups, but not automatic next writes.

| Item | Gate | Safe next shape |
|---|---|---|
| `AGENT_BRIDGE_CORRECTION_COSURFACE` enablement | Separate owner decision after backfill. | Short A/B or shadow window, top-k diff inspection, then decide whether to keep the env flag enabled. Do not infer this from the completed edge backfill. |
| SQLite `VACUUM` | Maintenance window. | Stop or freeze writers, back up `state.db` plus WAL/SHM if present, run integrity/quick checks, run VACUUM, verify size and `quick_check`. |
| Trigger recall production/default behavior | Production NO-GO without explicit owner packet. | Continue docs/read-only evidence, or use the dedicated candidate branch only under its Stage-2 constraints. |
| BioCortex / T6 / runtime influence | Owner-gated; current latest sampled evidence is `no_lift`. | Require explicit downstream labeled cases, nonzero lift, zero-regression packet, and rollback evidence. |
| Workflow-feedback higher-blast scopes | Blocked by runbook boundary. | Keep using documentation/durable-memory/runbook promotion only until stronger authorization exists for skill, retrieval, tool routing, prompt, profile, bootstrap, or runtime policy. |
| INT8 embedding column / Track A storage work | Parked / owner-gated. | Reopen only with fresh storage-ROI and owner approval; archived branches are audit refs, not merge candidates. |

The correction co-surface preflight found exactly one valid backfill candidate:

```text
correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682
  --corrects-->
session_handoff_present_voice_tts_subsystem_20260601
```

That maintenance write has now been executed by a parallel active session and
verified read-only from the live store:

```text
active_memories=667
active_feedback_corrections=5
corrects_edges=5
candidate_edge=(from, to, corrects, 1.4, 1782931382)
```

Do not repeat the backfill. The remaining correction co-surface decision is
runtime read-path enablement, which is a separate gate.

## Local Branch And Worktree Read

Current local branches:

- `master` carries the queue-audit commits on top of the correction preflight
  and post-backfill documentation line
- archive refs:
  - `archive/obsolete-daemon-embed-delegation-20260630`
  - `archive/obsolete-opencode-family-interactive-20260701`
  - `archive/parked-embed-int8-quant-20260630`
- dedicated-lane refs:
  - `backup/lswr-runtime-application-evidence-duplicate-f89868a`
  - `codex/aio2-trigger-pre-policy-hold-simulation-candidate`

There is no extra active worktree to clean. The archive refs should not be
merged. The two dedicated-lane refs need separate conflict or authorization
audits before any action.

## Board Read

Thread #102 still shows a correction LINK open question, but the implementation
branch has merged and the one-row backfill has since been completed. The
current live question is narrower: whether to approve a separate co-surface A/B
or shadow enablement window.

Thread #105 still carries older GTE open-question text in the digest. For the
local node, the runtime switch is closed as a no-op and the recall-eval corpus
health gate has since landed. Treat old GTE owner-review/canonical snapshot
lines as historical unless a new maintenance request names an exact live
mutation.

Thread #108 is closed enough for the workflow-feedback implementation stack:
the current action is repeated use and measurement of the runbook, not more
runtime plumbing.

Thread #90 has an older SEPL/L7 RFC. Do not use it as implicit authorization;
run a separate status audit before implementing anything from that RFC.

## Recommended Next Order

1. Publish this queue audit to repo, durable memory, work memory, and forum.
2. Do not repeat the correction backfill. If the owner explicitly opens the
   next correction gate, run only a bounded co-surface A/B or shadow enablement
   review.
3. If no owner gate opens, prefer non-conflicting read-only work:
   workflow-feedback usage evidence, report-quality improvement, queue audits,
   or stale-board cleanup proposals.
4. For implementation lanes, require an isolated worktree and fresh gate:
   trigger recall production candidate, LSWR runtime evidence duplicate, and
   any retrieval/runtime policy change.

## Evidence Checked

- `git status --short --branch`
- `git log --oneline --decorate -8`
- `git show --stat --patch 403db05` for the concurrent correction-preflight
  revalidation parent
- `git branch -vv`
- `git worktree list --porcelain`
- `forum_digest(status=open, thread_limit=40, posts_per_thread=50)`
- `forum_read` for recent #102, #105, #108, #90, and #110 posts
- `work_memory(op=list, cwd=/Data/CascadeProjects/agent-bridge)`
- `agent_presence_list(project=agent-bridge, max_idle_secs=900)`
- `mcp_lifecycle_digest(repo_root=/Data/CascadeProjects/agent-bridge)`
- read-only SQLite verification of the post-backfill `corrects` edge
- `/proc` environment scan showing visible `agent-bridge.real` processes do not
  have `AGENT_BRIDGE_CORRECTION_COSURFACE` set
- targeted reads of current reports and runbooks cited above

## Boundary

This report is deliberately conservative. It updates queue interpretation only.
It does not authorize any additional live backfill, env flag, schema migration,
ranking change, production recall behavior, daemon restart, deploy, branch
merge, or archival branch deletion.
