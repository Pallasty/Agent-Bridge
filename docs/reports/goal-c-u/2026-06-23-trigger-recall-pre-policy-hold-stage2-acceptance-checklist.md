# Trigger Recall Pre-Policy Hold Stage 2 Acceptance Checklist

Date: 2026-06-23

Scope: docs-only acceptance checklist for a future exact candidate commit from
the Stage-1 `pre_policy_hold_simulation_candidate` branch. This document does
not implement runtime code, does not approve merge or deploy, does not change
default `memory_search`, and does not authorize production `enforce_hold`.

## Verdict

`REVIEW-CHECKLIST-ONLY`.

Use this checklist only after the Stage-1 candidate branch produces an exact
commit. Until an approval packet names that commit, the candidate remains
review material.

## Candidate Under Review

The Stage-2 packet must fill these fields before review. For the original
Stage-1 authorization:

| Field | Required Value |
|---|---|
| candidate branch | `codex/trigger-pre-policy-hold-simulation-candidate` |
| candidate worktree | `/Users/pallasting/Projects/agent-bridge-trigger-pre-policy-hold-simulation-candidate` |
| candidate commit | exact non-empty SHA |
| approved mode | `pre_policy_hold_simulation` |
| base authorization | `87d709a docs(memory): authorize pre-policy hold candidate work` |
| reviewer | non-empty |
| forum decision post | non-empty |
| expiry/freshness | explicit date or `none_with_reason` |

For the Aio2 `/Data/...` amendment:

| Field | Required Value |
|---|---|
| candidate branch | `codex/aio2-trigger-pre-policy-hold-simulation-candidate` |
| candidate worktree | `/Data/CascadeProjects/agent-bridge-trigger-pre-policy-hold-simulation-candidate` |
| candidate commit | exact non-empty SHA |
| approved mode | `pre_policy_hold_simulation` |
| base authorization | `2026-06-23-trigger-recall-pre-policy-hold-stage1-aio2-data-worktree-amendment.md` |
| reviewer | non-empty |
| forum decision post | non-empty |
| expiry/freshness | explicit date or `none_with_reason` |

Do not accept a packet that says only "latest", "current branch", or "the
candidate". The exact commit is the review unit.

## Hard No-Go Conditions

Reject the candidate if any are true:

- default `memory_search` schema or behavior changed;
- candidate adds hidden parameters to default `memory_search`;
- candidate exposes the tool outside `Tier::Niche`;
- candidate deploys or installs a binary;
- candidate implements production `enforce_hold`;
- held query returns a bare `[]` instead of a status object;
- held query calls store FTS by default;
- withheld hits record coactivation or access-count side effects;
- raw query, key, content, or full scope path appears in output;
- tokenizer, schema, indexing, reindex, semantic retrieval, graph retrieval,
  memory writes, or graph-edge writes are touched without a new Stage-1
  amendment.

## Required Diff Audit

Run from the candidate worktree:

```bash
git diff --name-status <stage1-base>..HEAD
git diff --check <stage1-base>..HEAD
git diff -- crates/bridge/src/trigger_recall_opt_in.rs crates/bridge/src/mcp_tools.rs
```

Use `87d709a` as `<stage1-base>` for the original `/Users/...` authorization.
Use `39ea54f` as `<stage1-base>` for the Aio2 `/Data/...` amendment unless a
newer amendment explicitly names a different base.

Expected changed files:

- `crates/bridge/src/trigger_recall_opt_in.rs`
- `crates/bridge/src/mcp_tools.rs`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-simulation.md`

Any additional changed file requires explicit Stage-1 amendment before review.

## Required Behavior Checks

The candidate must prove these response states:

| Case | Expected Status | Store FTS | Visible Hits |
|---|---|---:|---:|
| approved accepted query | `returned_accepted` | yes | redacted baseline summaries |
| approved held query | `held_by_query_intent` | no by default | empty list inside object |
| held query with count audit | `held_by_query_intent` | yes, audit only | no visible withheld hits |
| malformed approval packet | `blocked_to_baseline` | baseline/fail-open allowed | baseline behavior |
| missing per-call opt-in | `blocked_to_baseline` | baseline/fail-open allowed | baseline behavior |
| operator disabled | `operator_disabled` | baseline/fail-open allowed | baseline behavior |
| non-`fts` mode | blocked/fail-open | baseline/fail-open allowed | baseline behavior |
| non-local scope | blocked/fail-open | baseline/fail-open allowed | baseline behavior |

For held queries, `baseline_count_status` must be:

- `not_requested_pre_policy_hold` when count audit is not requested;
- `count_audit_requested` only when `include_baseline_counts=true`.

## Required Safety Assertions

Tests or review evidence must show:

- `default_memory_search_unchanged=true`;
- `memory_search_mcp_called=false`;
- `records_coactivation=false` for withheld hits;
- `writes_memory=false`;
- `writes_graph_edges=false`;
- `changes_default_memory_search_schema=false`;
- `changes_production_retrieval_default=false`;
- `runs_semantic_retrieval=false`;
- `runs_graph_retrieval=false`;
- `may_enforce_hold=false`.

## Required Tool-Surface Checks

The MCP wrapper, if present, must be:

- named `trigger_recall_opt_in_pre_policy_hold_simulation`;
- registered as `Tier::Niche`;
- visible under `AGENT_BRIDGE_TOOL_PROFILE=all`;
- absent from standard / Codex essential profiles;
- documented as candidate/opt-in, not default retrieval.

## Required Commands

Minimum Stage-2 command gate:

```bash
cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
cargo check -p ab-bridge --lib
git diff --check
```

Wider evidence before approval:

```bash
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
```

Required thresholds:

| Metric | Required |
|---|---:|
| trigger opt-in tests | all pass |
| true hits lost by shadow gate | `0` |
| positive cases held | `0` |
| baseline false hits after shadow gate | `0` |
| accepted order drift | `0` |
| raw query/key/content leaks | `0` |
| held responses as bare arrays | `0` |

Do not run unbounded full-file `rustfmt --check` over
`crates/bridge/src/mcp_tools.rs` while the known large formatter diff remains.

## Stage-2 Decision Template

Use this exact shape for a future approval post:

```text
Decision: APPROVED-FOR-PRE-POLICY-HOLD-SIMULATION
Candidate commit: <sha>
Approved mode: pre_policy_hold_simulation
Stage-1 authorization: 87d709a
Default memory_search unchanged: yes
Tool exposure: Tier::Niche only
Held response object, not []: yes
Held default store search: no
Count audit search explicitly gated: yes
Operator disable fail-open: yes
Raw query/key/content leaks: 0
Regression anchor: aio2_trigger_recall_baseline_acceptance_shadow_20260623
Expires: <date or none_with_reason>
```

Without this exact Stage-2 decision, candidate code remains non-authorizing.

## Current Next Action

Wait for the Stage-1 candidate commit from #3991, then run this checklist
against that exact commit. Do not merge or deploy before the Stage-2 decision.
