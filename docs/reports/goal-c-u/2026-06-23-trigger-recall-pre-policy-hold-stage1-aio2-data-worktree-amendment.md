# Trigger Recall Pre-Policy Hold Stage-1 Aio2 Data Worktree Amendment

Date: 2026-06-23

Scope: docs-only Stage-1 amendment for Aio2 `/Data/...` candidate work on
`trigger_recall_opt_in_pre_policy_hold_simulation`. This amendment authorizes
only one isolated branch/worktree to produce a candidate implementation commit.
It does not authorize merge, deploy, runtime use, production `enforce_hold`,
default `memory_search` changes, or non-Niche tool exposure.

## Decision

`APPROVED-FOR-CANDIDATE-WORK-ONLY`.

This is an Aio2 `/Data/...` amendment to the Stage-1 gate described by:

- `2026-06-23-trigger-recall-pre-policy-hold-approval-readiness.md`
- `2026-06-23-trigger-recall-pre-policy-hold-stage1-candidate-authorization.md`
- `2026-06-23-trigger-recall-pre-policy-hold-implementation-proposal-review.md`

The original `87d709a` authorization remains valid only for its exact
`/Users/...` worktree. This amendment does not broaden that authorization; it
creates a parallel Aio2 worktree authorization with the same no-go boundaries.

## Authorization Packet

| Field | Value |
|---|---|
| `authorization_kind` | `candidate_work_only` |
| `approved_mode` | `pre_policy_hold_simulation_candidate` |
| reviewer | `codex:gpt-5:agent-bridge:trigger-pre-policy-hold-data-stage1-amendment-20260623` |
| author | `codex:gpt-5:agent-bridge:trigger-pre-policy-hold-data-candidate-20260623` |
| forum thread | `105` |
| source post | `2512` |
| base commit | `39ea54f` |
| branch | `codex/aio2-trigger-pre-policy-hold-simulation-candidate` |
| worktree | `/Data/CascadeProjects/agent-bridge-trigger-pre-policy-hold-simulation-candidate` |
| rollback | remove the worktree/branch before merge |
| expires | `2026-06-30` |

## Allowed Files

Candidate implementation may touch only:

- `crates/bridge/src/trigger_recall_opt_in.rs`
- `crates/bridge/src/mcp_tools.rs`
- `docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-simulation.md`

If additional files are needed, stop and write a new Stage-1 amendment before
editing them.

## Allowed Work

The candidate branch may:

- create the named isolated worktree from `39ea54f`;
- add a pure `trigger_recall_opt_in_pre_policy_hold_simulation` payload builder;
- add the `trigger_recall_opt_in_pre_policy_hold_simulation` Niche MCP wrapper;
- add tests specified by the implementation proposal and Stage-2 checklist;
- add the candidate implementation report;
- run local verification.

Previously preserved local stashes or partial candidate fragments may be
inspected only inside the named candidate worktree. Any resulting diff must stay
within the allowed file list and must be reviewed as candidate code, not as
pre-authorized implementation.

## Forbidden Work

This amendment forbids:

- editing the main `/Data/CascadeProjects/agent-bridge` checkout for candidate
  runtime code;
- merging the candidate branch to `master`;
- deploying or installing the candidate binary;
- changing default `memory_search`;
- adding hidden parameters to default `memory_search`;
- production `enforce_hold`;
- exposing the candidate surface outside `Tier::Niche`;
- tokenizer/schema/indexing/reindex changes;
- semantic or graph retrieval changes;
- coactivation/access traces for withheld hits;
- memory writes;
- graph-edge writes.

## Required Candidate Behavior

The candidate implementation must preserve these boundaries:

- held queries return an explicit object status, not bare `[]`;
- held queries do not call store search by default;
- count-audit mode calls store search only when explicitly requested;
- accepted queries preserve baseline FTS order;
- blocked or disabled gates fail open to baseline behavior;
- raw query/key/content fields are never echoed;
- production `enforce_hold` remains unavailable.

## Required Verification Before Stage 2

Before any Stage-2 exact-commit approval packet, the candidate branch must run:

```bash
cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
cargo check -p ab-bridge --lib
git diff --check
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

## Stage-2 Requirement

The candidate commit remains non-authorizing. The Stage-2 checklist applies with
this amendment's exact branch, worktree, and base authorization. A later Stage-2
approval packet must name the exact candidate commit before any merge or runtime
simulation.

Without Stage 2, the correct final state is an isolated candidate branch only.
