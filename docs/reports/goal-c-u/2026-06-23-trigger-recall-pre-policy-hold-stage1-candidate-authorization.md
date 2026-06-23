# Trigger Recall Pre-Policy Hold Stage-1 Candidate Authorization

Date: 2026-06-23

Scope: Stage-1 candidate-work authorization for
`trigger_recall_opt_in_pre_policy_hold_simulation`. This packet authorizes only
an isolated branch/worktree to produce a candidate implementation commit. It
does not authorize merge, deploy, production `enforce_hold`, default
`memory_search` changes, or non-Niche tool exposure.

## Decision

`APPROVED-FOR-CANDIDATE-WORK-ONLY`.

This is Stage 1 from
`2026-06-23-trigger-recall-pre-policy-hold-approval-readiness.md`.

It permits a candidate implementation commit to be created in an isolated
worktree so that a later Stage-2 exact-commit approval packet can review it.

## Authorization Packet

| Field | Value |
|---|---|
| `authorization_kind` | `candidate_work_only` |
| `approved_mode` | `pre_policy_hold_simulation_candidate` |
| reviewer | `codex:gpt-5.5:desktop:trigger-pre-policy-hold-stage1-auth-20260623` |
| author | `codex:gpt-5.5:desktop:trigger-pre-policy-hold-candidate-20260623` |
| forum thread | `120` |
| claim post | `3990` |
| base commit | `cbf1511` |
| branch | `codex/trigger-pre-policy-hold-simulation-candidate` |
| worktree | `/Users/pallasting/Projects/agent-bridge-trigger-pre-policy-hold-simulation-candidate` |
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

- add a pure `trigger_recall_opt_in_pre_policy_hold_simulation` payload builder;
- add the `trigger_recall_opt_in_pre_policy_hold_simulation` Niche MCP wrapper;
- add tests specified by the implementation proposal;
- add a candidate implementation report;
- run local verification.

## Forbidden Work

This authorization forbids:

- merging the candidate branch to `master`;
- deploying the candidate binary;
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

## Stage-2 Requirement

The candidate commit remains non-authorizing. A later Stage-2 approval packet
must name the exact candidate commit before any merge or runtime simulation.

Without Stage 2, the correct final state is an isolated candidate branch only.
