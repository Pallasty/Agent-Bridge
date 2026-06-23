# Trigger Recall Pre-Policy Hold Implementation Proposal Review

Date: 2026-06-23

Scope: docs-only review of
`2026-06-23-trigger-recall-pre-policy-hold-implementation-proposal.md`.
This review does not implement runtime behavior, does not authorize production
`enforce_hold`, does not change default `memory_search`, does not register a new
MCP tool, and does not write memory or graph state.

## Verdict

`APPROVED-FOR-STAGE-1-AUTHORIZATION-PACKET-ONLY`.

The implementation proposal is specific enough to support a docs-only Stage-1
candidate-work authorization packet for
`pre_policy_hold_simulation_candidate`.

Post-sync status: `87d709a` now satisfies that Stage-1 gate for the exact
`/Users/...` worktree named in that packet, and `1dd3dbf` adds a Stage-2
acceptance checklist. This review still does not authorize runtime code.
Candidate work in the current `/Data/...` checkout remains blocked until a
Stage-1 amendment names an exact `/Data/...` branch/worktree and allowed file
list. Merge/runtime use remains blocked until a later Stage-2 packet names an
exact implementation commit, exact approved mode, reviewer, forum post id,
regression results, and rollback path.

## Reviewed Inputs

- `docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-implementation-proposal.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-schema-review.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-approval-packet-schema.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-enforce-hold-approval-packet-schema.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-approval-readiness.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-stage1-candidate-authorization.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-stage2-acceptance-checklist.md`
- Forum thread 105 through post `#2511`
- Current repo state before this review: `master...origin/master`, rev-list
  `0 0`, worktree clean.

## Review Findings

### Finding 1 - Proposed Surface Is Correctly Separate

The proposal names a new Niche/all-profile surface:

```text
trigger_recall_opt_in_pre_policy_hold_simulation
```

It explicitly rejects adding a hidden parameter to default `memory_search`.
That matches all prior gates and preserves the bare hit-list contract for the
default tool.

### Finding 2 - Proposed File Scope Is Narrow

The proposal limits future code to:

- `crates/bridge/src/trigger_recall_opt_in.rs`;
- `crates/bridge/src/mcp_tools.rs`;
- one implementation report.

It does not propose store crate changes, tokenizer/schema/indexing/reindex
changes, graph retrieval, semantic retrieval, memory writes, or graph writes.

That is an acceptable first implementation boundary if later approved.

### Finding 3 - Approval Validation Is Explicit Enough

The proposal requires a future approval packet to validate:

- exact schema;
- `packet_status=approved_for_pre_policy_hold_simulation`;
- `approved_mode=pre_policy_hold_simulation`;
- exact implementation commit;
- regression anchor;
- unchanged default `memory_search`;
- raw query/key/content exclusion;
- rollback field.

If approval is missing or malformed, the future wrapper must return
`blocked_to_baseline` and fail open to baseline behavior.

Review clarification: any approval packet without an exact implementation
commit is non-authorizing, even if it contains a plausible design or reviewer
language.

### Finding 4 - Execution Semantics Preserve The Pre-Policy Boundary

The future tool order is correct:

1. validate approval;
2. validate runtime gates and redaction;
3. classify query intent before baseline search;
4. hold rejected queries without store search by default;
5. search only for explicit count-audit or accepted queries;
6. preserve baseline order for accepted queries;
7. fail open to baseline behavior when blocked.

This protects the main risk from the gated baseline trial: held-query evidence
does not need to create baseline telemetry unless explicitly requested.

### Finding 5 - Test Plan Covers The Critical Failure Modes

The proposed tests cover:

- held query object status;
- no store search for held queries by default;
- count-audit store search without visible hits;
- accepted baseline order preservation;
- missing approval fail-open;
- operator disable fail-open;
- non-`fts` and non-local scope blocks;
- raw payload rejection;
- default `memory_search` unchanged.

That is the right test surface for a future approval packet.

### Finding 6 - Profile Boundary Must Be Rechecked In Implementation

The proposal says the future tool should be Niche/all-profile and not in the
default Codex essential profile.

Future implementation must include an explicit profile exposure assertion. The
installed-binary gated-batch review proved this matters: trigger control-plane
tools are intentionally absent from lean/default profiles.

## Required Clarifications For Stage-1 Or Amendment

The `87d709a` Stage-1 candidate-work authorization packet resolves these items
for the named `/Users/...` worktree only. Any Aio2 `/Data/...` amendment must
resolve the same items before candidate work starts in this environment:

- exact approval schema to use:
  candidate-work authorization, not the Stage-2 exact-commit approval packet;
- exact approved mode:
  `pre_policy_hold_simulation_candidate`;
- exact branch and worktree path;
- exact allowed files;
- exact forbidden behavior:
  no merge, no deploy, no default `memory_search` change, no production
  `enforce_hold`, no non-Niche exposure;
- exact runtime enable env:
  `AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN=1`;
- exact runtime disable env:
  `AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE=1`;
- whether `include_baseline_counts=true` is allowed in the first code slice or
  deferred to a second count-audit slice;
- whether accepted responses may include visible hit summaries, or only
  redacted hit summaries, in the first code slice.

## Decision

This review initially approved exactly one next action:

Write a docs-only Stage-1 candidate-work authorization packet for
`pre_policy_hold_simulation_candidate`.

That action is now satisfied by `87d709a` only for the isolated branch/worktree
named in that packet. `1dd3dbf` adds the Stage-2 acceptance checklist for a
future exact candidate commit. Neither document approves merge, deploy, runtime
use, production `enforce_hold`, or candidate work in a different checkout.
Stage-2 exact-commit approval is still required after a candidate commit exists.

Post-review synchronization note: `87d709a` has already added a Stage-1
candidate-work authorization packet, but that packet names the exact worktree
`/Users/pallasting/Projects/agent-bridge-trigger-pre-policy-hold-simulation-candidate`.
The current Aio2 checkout is `/Data/CascadeProjects/agent-bridge`, and that
`/Users/...` path is not present here. This review does not expand the
authorization to the current checkout. Candidate work in this environment still
requires a Stage-1 amendment naming a `/Data/...` branch/worktree.

## Still No-Go

Still not authorized:

- implementing `trigger_recall_opt_in_pre_policy_hold_simulation` in the
  current `/Data/...` checkout without a Stage-1 amendment;
- implementing production `enforce_hold`;
- changing default `memory_search`;
- adding hidden default-search parameters;
- returning bare `[]` for held queries;
- coactivation/access traces for withheld hits;
- memory or graph writes;
- semantic or graph retrieval;
- profile exposure in default Codex essential tools.

## Next Gate

Next safe action: use the Stage-1 authorized `/Users/...` worktree if operating
on that host, or write a Stage-1 amendment for an Aio2 `/Data/...` worktree
before producing candidate code here. The amendment should name an exact path,
for example
`/Data/CascadeProjects/agent-bridge-trigger-pre-policy-hold-simulation-candidate`,
if that is the intended candidate worktree.

Candidate code may be produced only in a named isolated branch/worktree.
Merge/runtime use still requires a separate Stage-2 approval packet that names
an exact candidate implementation commit.
