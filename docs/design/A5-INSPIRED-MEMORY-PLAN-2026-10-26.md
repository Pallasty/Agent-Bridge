# A5-inspired memory work: implementation plan

## Intent and status

Owner request on 2026-10-26: “很好！我们先记忆你的研究结论，再规划落地你建议的目标。”
The previous scope was static A5 research; this request adds durable recall and
implementation planning. The ordering and technical choices below are the
working agent's recommendations. This document records a plan, not completed
feature implementation, runtime activation, or measured benefit.

Outcome: reduce unnecessary repeated memory material without losing current
commitments, corrections, or source validity. First establish whether the
existing consumer can distinguish prior delivery from current visibility.

Research is saved under memory key `research_a5_static_review_20261025`.
Full packet: `/Data/CascadeProjects/research/a5-review-20261025/REPORT.txt`.
Report SHA256: `7d013757dfb7b3893b528149d5da50846b78a7bbc97451c6c0110904e8a9fc7f`.
A5 was statically inspected only; runtime and task benefit remain `not_run`.
Its obfuscated strings and prompts are design evidence, not verified controls.

## Current implementation evidence

Inspected AB HEAD: `2485fbad3535f51f85eedeb2fd22564205842994`.

- `crates/bridge/src/mcp_tools.rs`, `SessionBootstrapTool`: semantic bootstrap
  already uses MMR, with a protected handoff prefix. The input schema carries
  cwd/query/frontend/error_hint, but no consumer context epoch or visible-memory
  receipt. MMR diversifies one response; it does not track current visibility.
- `crates/bridge/src/hooks/ab-memory-hook.sh`: the foreground hook counts turns
  per session and injects on turns 1, 9, 17, ... at the default cooldown. Its MCP
  request carries the query; its output is an `additionalContext` string. The
  inspected path has no host acknowledgment that this text remains available
  after context compaction. A separate recovery-hint helper already deduplicates
  a specific presentation block; it is not general memory visibility evidence.
- `crates/bridge/src/retrieval_outcome.rs`: surfacing/use attribution serves
  feedback rules. A historical surfacing or read is not proof that its exact
  content remains in the current model context.
- `dream_digest.rs` and `digest_read.rs`: author-source revisions and a guarded
  digest read already exist. Preserve them; do not duplicate these mechanisms
  or describe the single guarded read as protecting every retrieval surface.

Natural repeated-injection frequency, token cost, and owner cost are currently
unknown. Neither repeated retrieval nor a synthetic repeated fixture proves an
unnecessary real-world injection. The hook's installed/live use on each client
is also unverified in this planning pass.

## Goal 1: establish a safe version-aware injection decision

First deliverable: a bounded diagnostic over an existing foreground route,
with explicit `unknown` visibility. Do not begin by suppressing results.

1. Select one existing consumer and verify its actual route, configuration and
   available lifecycle evidence. Inspect existing logs read-only, at most three
   already available relevant sessions; do not generate tasks or enable a
   collector to obtain examples. Keep private bodies out of committed reports.
2. For a candidate repeated delivery, record scope, key, exact rendered material
   revision, delivery/turn identity, and any authoritative context-reset or
   compaction boundary. Count confirmed repeated material separately from
   uncertain visibility and from useful refreshes. Use bytes as bytes; do not
   report token savings without the actual tokenizer or clear estimation label.
3. Establish whether the consumer can supply a current-context epoch and an
   acknowledgment of the exact retained content. If unavailable, close the
   diagnostic with `VISIBILITY_UNKNOWN`; no suppression is justified. Do not
   invent a session-wide seen-key cache to bridge this gap.
4. If real redundant delivery and adequate consumer evidence are demonstrated,
   implement a narrow optional filter at that consumer's injection boundary.
   Keep direct `memory_get`/`memory_search` available and preserve explicit user
   requests for content. Avoid changing global ranking or adding a daemon.

Conditional filter identity: consumer + session + context epoch + scope + key
+ revision of the actual rendered material. Full memory-content and lifecycle
revisions must also be checked where needed; `updated_at` alone is insufficient.
Same text across different scopes is not automatically interchangeable.

Decision ordering: apply existing eligibility/source checks first; then consider
visibility. Unknown visibility leaves otherwise eligible material available;
it never overrides an existing stale-source withholding decision. Do not mark
failed or partial delivery as seen. Changes to rendered projections, source
revision, epoch, or consumer invalidate the corresponding visibility assumption.

Acceptance for a future filter:

- Same eligible version confirmed retained in the same epoch may be omitted.
- Changed content, changed lifecycle/scope, new session/epoch, context reset,
  stale receipts, failed delivery, and unknown retention cannot silently suppress
  needed eligible material. Withdrawn sources retain the existing withholding.
- Current commitments, safety constraints, corrections and protected handoffs
  keep their existing inclusion policy in the first increment.
- Delayed decisions cannot mutate a newer turn's visibility state. No new
  asynchronous prefetch service is introduced just to test this condition.
- Fixed-input comparison preserves essential task facts and all source guards;
  any unsafe omission rejects the candidate. Reduced bytes alone is insufficient.
- Feature tests cover these transitions using isolated state. Natural usefulness
  remains unknown until ordinary-task evidence exists; fixture passes establish
  only the filter mechanics. Default behavior and a direct rollback remain intact.

## Goal 2: explain why a rejected suggestion is worth reconsidering

Conditional next priority, not an active background campaign. First find an
existing foreground proposal/review entry and a real repetition problem. If
neither exists, retain this as a design candidate; do not build an Inbox service.

Represent the original item, rejection, scope, supporting evidence revisions,
and new evidence separately. A changed title or paraphrase is not a new reason.
Require an inspectable `why_now` grounded in materially changed evidence before
surfacing the same rejected suggestion again. Revalidate history at submission;
if history changed during evaluation, re-evaluate instead of committing stale
reasoning. Unknown history must not be labeled verified novelty.

Acceptance: unchanged/paraphrased rejected items are withheld; material evidence
changes are explained; in-progress/completed items do not become duplicate work;
separate scopes stay separate; zero suggestions is a valid result. Validate
mechanical identity separately from semantic judgment. A fixture cannot prove
reduced annoyance. Do not equate wake-id deduplication with this behavior.

## Goal 3: publish a compact overview without losing its evidence

Conditional after a demonstrated compression defect or measurable burden.
Reuse the digest author/gate/read machinery. Construct a bounded candidate,
preserve necessary detail, read back the actual saved bytes, check source
revisions at publication, and retain the prior artifact for rollback. Explicitly
list the facts, constraints, exceptions and unresolved conflicts that must survive.

Acceptance: source edits during preparation invalidate the candidate; missing
detail/readback rejects publication; failed publication preserves the old
artifact; restored content matches the retained prior version. These mechanical
checks do not establish semantic faithfulness; that requires a separate
claim-by-claim review against frozen inputs. Do not migrate SQLite to Markdown
or activate automatic maintenance as part of this increment.

## Delivery and boundaries

Completed here: research memory saved and read back; existing source paths
inspected; conditional goals, acceptance and stop conditions recorded.
Goal 1 steps 1–3 were subsequently completed on 2026-10-26. See the
[bounded diagnostic](../reports/2026-10-26-a5-memory-visibility-diagnostic.md).
It found repeated static attachments and installed v4/source v5 drift, but
closed with `VISIBILITY_UNKNOWN`: full source revisions and per-request retained
context evidence are unavailable on the inspected route. Do not advance to the
conditional filter based on historical delivery alone.
The follow-up [host interface assessment](../reports/2026-10-26-a5-host-retention-interface.md)
also completed on 2026-10-26. Existing hooks, status usage and internal compact
metadata did not establish a supported current-request retention receipt on the
inspected route. Close the investigation here; restart only with concrete host
capability evidence or an explicitly changed goal, not another generic stage.
Goal 1 filter, Goal 2 and Goal 3 are not implemented or tested by this document.

Use the current roadmap as the authority for collection state: R4 retains
`HOLD_TRIAL_TOPOLOGY`, R4-A remains `FROZEN`, active R7 M2 sample pursuit remains
`HOLD`. This plan does not reopen them, install A5, enable background work, or
authorize deployment. No new CI/workflow dispatch. Preserve existing user data.
