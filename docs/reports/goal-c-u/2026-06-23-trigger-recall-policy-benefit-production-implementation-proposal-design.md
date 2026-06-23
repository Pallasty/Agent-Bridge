# Trigger Recall Policy-Benefit Production Implementation Proposal Design

Date: 2026-06-23

Schema:
`agent_bridge.memory.trigger_recall.policy_benefit.production_implementation_proposal_design.v0`

Scope: docs-only bridge between the repaired live Mac
`policy_benefit_eval.v0` evidence and any future production implementation
proposal for trigger-recall pre-policy hold.

This document does not implement production `enforce_hold`, does not authorize
production behavior, does not change default `memory_search`, does not promote
MCP tool exposure, and does not write memory, graph, index, semantic, or
coactivation state.

## Verdict

`DESIGN-PROPOSAL-ONLY / IMPLEMENTATION-NO-GO`

The repaired live Mac policy-benefit gate is strong enough to become a required
evidence input for any future production implementation proposal. It is not
authorization to write runtime code or enable production hold behavior.

Current authorization state:

```text
production_enforce_hold_authorized=false
runtime_enablement_authorized=false
implementation_code_authorized=false
default_memory_search_change_authorized=false
non_niche_exposure_authorized=false
```

## Relationship To Existing Production Lane

This file does not replace the earlier pre-policy-hold production lane.

The earlier lane remains parked by:

```text
docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-production-implementation-rejection-packet.md
```

The repaired policy-benefit evidence only adds a new acceptance requirement for
future reopening. It does not supersede that rejection packet and does not
convert review readiness into implementation approval.

## Inputs

Policy-benefit repair evidence:

| Item | Value |
|---|---|
| repair commit | `7171e7d test(memory): repair live policy benefit gate` |
| review packet commit | `281b001 docs(memory): add policy benefit production review packet` |
| branch | `codex/goal-c-policy-benefit-repair-20260623` |
| parent master | `7c79675 test(memory): add live mac policy benefit eval` |
| repair report | `docs/reports/goal-c-u/2026-06-23-trigger-recall-policy-benefit-repair.md` |
| production review packet | `docs/reports/goal-c-u/2026-06-23-trigger-recall-policy-benefit-production-review-packet.md` |
| memory key | `trigger_recall_policy_benefit_production_review_packet_20260623_281b001` |
| board posts | thread `#120`, posts `#4046` and `#4047` |

Live board state at proposal time:

```text
forum_read(thread_id=120, since_post_id=4047) returned 0 posts.
owner_decision=pending
```

## Required Evidence Chain For Any Future Reopen

Any future production implementation proposal must satisfy both chains:

| Chain | Required Evidence |
|---|---|
| pre-policy-hold runtime safety | same-head smoke proves held path is explicit, default-off, redacted, and fail-open |
| policy-benefit quality | same-head or freshness-window live Mac policy-benefit eval proves positive cases preserved and false hits removed |

Neither chain is sufficient by itself.

The pre-policy-hold chain answers: can a protected opt-in surface avoid unsafe
runtime side effects?

The policy-benefit chain answers: does the candidate hold policy actually remove
bad baseline hits while preserving expected positives?

## Minimum Future Proposal Shape

A later production implementation proposal, if explicitly requested, should use
a separate schema:

```text
agent_bridge.memory.trigger_recall.policy_benefit.production_implementation_proposal.v0
```

It must name:

| Field | Requirement |
|---|---|
| implementation branch | exact branch/worktree |
| implementation commit | exact commit under review, once code exists |
| approved mode | `audit_only` or `pre_policy_hold_candidate`; not production `enforce_hold` |
| runtime surface | Niche/all-profile explicit opt-in only |
| default search | unchanged |
| operator enable | explicit env or config gate |
| operator disable | explicit fail-open kill switch |
| per-call opt-in | required |
| scope | exact local project scope |
| retrieval mode | `fts` only unless separately approved |
| rollback | command and verification evidence |

## Policy-Benefit Acceptance Matrix

Before any future code proposal can be accepted, the same-head or
freshness-window live Mac policy-benefit run must meet:

| Metric | Required |
|---|---:|
| full live corpus expected refs | `30/30` |
| full live corpus ready | `true` |
| policy-benefit positive baseline hits | `all scoped positives` |
| positive cases held | `0` |
| true hits lost by shadow gate | `0` |
| accepted order drift | `0` |
| baseline false hits after gate | `0` |
| false hits removed by shadow gate | `> 0` |
| contract_passed | `true` |
| ready_for_production_review | `true` |
| production_enforce_hold_authorized | `false` until a separate owner approval exists |

The current repaired evidence met these thresholds for the scoped 29-case
policy-benefit contract and kept `nexus_wuxing_math` in the separate 30-case CJK
fallback track.

## Required Pre-Code Verification

Immediately before reopening implementation code, rerun:

```text
/home/pallasting/.local/bin/agent-bridge.real doctor --json
scripts/verify-trigger-recall-pre-policy-hold-runtime-smoke.sh
CARGO_BUILD_JOBS=2 cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
CARGO_BUILD_JOBS=2 cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --policy-benefit-fixture
```

And on the Mac live store:

```text
CARGO_BUILD_JOBS=2 cargo run --manifest-path /Users/pallasting/Projects/agent-bridge-trigger-policy-benefit-live-mac/Cargo.toml \
  -p ab-bridge --no-default-features --example trigger_recall_eval -- --check-corpus

CARGO_BUILD_JOBS=2 cargo run --manifest-path /Users/pallasting/Projects/agent-bridge-trigger-policy-benefit-live-mac/Cargo.toml \
  -p ab-bridge --no-default-features --example trigger_recall_eval -- --policy-benefit-live-mac
```

## Implementation Boundary

If a future owner packet reopens implementation, the first acceptable code slice
must still be default-off and reviewable:

- no default `memory_search` behavior, schema, or order changes;
- no compact/essential exposure;
- no hidden parameter on default `memory_search`;
- no tokenizer, schema, index, or reindex change;
- no memory writes;
- no graph writes;
- no semantic or graph retrieval;
- no coactivation for withheld hits;
- no production runtime enablement;
- held responses must be objects with explicit status, never bare `[]`;
- rejected query intent must fail open unless every authorization gate passes.

## Approval Packet Required Before Code

Before code can be written, a new owner packet must supersede the parked state
and include:

```json
{
  "schema": "agent_bridge.memory.trigger_recall.policy_benefit.production_implementation_approval.v0",
  "owner_decision": "approve_candidate_code_only",
  "approved_mode": "pre_policy_hold_candidate",
  "approved_implementation_branch": "TBD",
  "approved_implementation_commit": "TBD-after-candidate-exists",
  "approved_runtime_surface": "Niche/all-profile explicit opt-in only",
  "policy_benefit_review_packet_commit": "281b001",
  "policy_benefit_repair_commit": "7171e7d",
  "default_memory_search_change_authorized": false,
  "production_enforce_hold_runtime_enable_authorized": false,
  "runtime_enablement_requires_separate_post_code_review": true,
  "rollback_required": true,
  "expires_at": "TBD"
}
```

Code-only approval must not enable production runtime behavior. Runtime
enablement needs a separate post-code review packet naming the exact candidate
commit and fresh verification evidence.

## Next Gate

Allowed next:

- post this proposal design to thread `#120`;
- save it as an AB memory decision;
- wait for an explicit owner decision before runtime code.

Blocked until a new owner packet exists:

- candidate code implementation;
- production runtime enablement;
- default retrieval changes;
- deploy or GTE cutover tied to this policy.
