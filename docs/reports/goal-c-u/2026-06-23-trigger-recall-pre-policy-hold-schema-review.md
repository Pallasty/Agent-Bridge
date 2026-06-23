# Trigger Recall Pre-Policy Hold Schema Review

Date: 2026-06-23

Scope: docs-only review of
`2026-06-23-trigger-recall-pre-policy-hold-approval-packet-schema.md`.
This review does not implement runtime behavior, does not authorize production
`enforce_hold`, does not change default `memory_search`, does not register a new
MCP tool, and does not write memory or graph state.

## Verdict

`APPROVED-FOR-IMPLEMENTATION-PROPOSAL-ONLY`.

The approval-packet schema is sufficient as a gate for the next docs-only step:
an implementation proposal for `pre_policy_hold_simulation` that names exact
files, tests, feature/kill switches, and rollback boundaries.

It is not sufficient to approve code implementation. Runtime work remains
`IMPLEMENTATION-NO-GO` until a later approval packet names an exact
implementation commit and exact approved mode.

## Reviewed Inputs

- `docs/reports/goal-c-u/2026-06-23-trigger-recall-enforce-hold-production-proposal.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-enforce-hold-approval-packet-schema.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-approval-packet-schema.md`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-gated-batch-review-packet.md`
- Forum thread 120 through post `#3983`
- Current repo state: `master...origin/master`, rev-list `0 0`, worktree
  clean before this review.

## Review Findings

### Finding 1 - Scope Is Correctly Non-Runtime

The schema explicitly says:

- no runtime behavior;
- no production `enforce_hold`;
- no default `memory_search` change;
- no new MCP tool registration;
- no memory or graph writes.

This matches the current authorization ladder. The schema can govern future
approval packets, but it cannot itself authorize implementation.

### Finding 2 - Mode Vocabulary Is Narrow Enough

The schema allows only:

- `audit_only`;
- `pre_policy_hold_simulation`.

It explicitly excludes:

- `enforce_hold`;
- `hybrid`;
- `semantic`;
- hidden default `memory_search` parameters.

Review clarification: `pre_policy_hold_simulation` is the canonical approval
mode name. Earlier shorthand such as `pre_policy_hold` in proposal prose must
not be treated as approval vocabulary.

### Finding 3 - Held Responses Are Safely Distinct From Empty Search

The schema requires held queries to return an explicit object response with:

- `status=held_by_query_intent`;
- redacted `query_intent` reason;
- `baseline.store_search_called=false` by default;
- `memory_search_mcp_called=false`;
- `baseline_count_status=not_requested_pre_policy_hold`.

That preserves the important distinction between:

- ordinary empty search;
- policy-held query;
- blocked/fail-open baseline behavior.

### Finding 4 - Pre-Policy Boundary Is Correct

The schema requires rejected query intent to short-circuit before baseline
store search by default. It also excludes coactivation traces, access-count
bumps, memory writes, graph writes, semantic retrieval, and graph retrieval for
withheld hits.

The only count-audit exception is explicit and labeled:

```text
include_baseline_counts=true
baseline_count_status=count_audit_requested
```

That exception remains evidence-only and must not become normal production
behavior.

### Finding 5 - Approval Packet Requirements Are Strong Enough

Future approval must name:

- exact schema;
- exact approved mode;
- exact implementation commit;
- author and reviewer;
- forum thread/post;
- regression anchor;
- default search unchanged flag;
- redaction flags;
- rollback/disable path.

This is strong enough to avoid accidental approval by vague forum language or
memory notes.

Review clarification: a proposal-only packet may discuss a future commit, but
it is non-authorizing unless it names an exact implementation commit and uses
the exact approval decision shape from the schema.

### Finding 6 - Test Gate Is Sufficient For Proposal Review

The required future implementation gate includes:

- trigger opt-in lib tests;
- trigger eval example tests;
- Aio2 baseline acceptance audit;
- `cargo check -p ab-bridge --lib`;
- `git diff --check`.

Required thresholds preserve the current safety line:

- true hits lost by shadow gate: 0;
- positive cases held: 0;
- baseline false hits after shadow gate: 0;
- accepted order drift: 0;
- raw query/key/content leaks: 0;
- held responses as bare arrays: 0.

That is sufficient for a future implementation proposal. It is still not a
runtime approval.

## Decision

This schema review approves exactly one next action:

Write a docs-only implementation proposal for `pre_policy_hold_simulation`.

The proposal must name:

- exact files expected to change;
- exact pure/helper functions to add or reuse;
- exact MCP surface name or proof that no MCP surface is added;
- exact tests and assertions;
- feature/runtime env names;
- operator disable path;
- fail-open behavior;
- rollback plan;
- verification commands.

The proposal must not include code changes, and it must not approve production
`enforce_hold`.

## Still No-Go

Still not authorized:

- implementing runtime `pre_policy_hold_simulation`;
- implementing production `enforce_hold`;
- changing default `memory_search`;
- adding hidden parameters to default `memory_search`;
- returning bare `[]` for held queries;
- touching tokenizer/schema/indexing/reindex;
- semantic or graph expansion;
- coactivation/access traces for withheld hits;
- memory or graph writes.

## Next Gate

Next safe action: docs-only implementation proposal for
`pre_policy_hold_simulation`.

After that proposal exists, a separate approval packet must name an exact
implementation commit before any runtime code is written or merged.
