# Trigger Recall Enforce Hold Production Proposal

Date: 2026-06-23

Scope: production-facing proposal and approval gate only. This document does
not implement `enforce_hold`, does not change default `memory_search`, does not
register a new runtime tool, does not write memory or graph edges, and does not
deploy behavior.

## Verdict

`DESIGN-PROPOSAL-ONLY`.

`enforce_hold` remains `IMPLEMENTATION-NO-GO` until a later operator/reviewer
approval packet explicitly authorizes an implementation slice.

The evidence now supports writing this proposal:

- Slice 1 read-only status and transition gate are landed.
- Slice 2 gated baseline trial is landed.
- Redacted gated batch diagnostics are landed.
- Batch diagnostics review is `APPROVED-AS-REVIEW-EVIDENCE`.
- Local Aio2 audit still reports true hits lost 0, positive cases held 0, and
  baseline false hits 21 before the shadow gate / 0 after it.

That evidence is still not production authorization.

## Proposed Runtime Shape

The first production candidate should be a separate protected opt-in surface,
not a hidden option on default `memory_search`.

Suggested future names:

| Layer | Candidate Name | Purpose |
|---|---|---|
| pure policy | `trigger_recall_query_intent` | deterministic allow/hold reason labels |
| wrapper | `trigger_recall_opt_in_enforce_hold_trial` | pre-policy hold simulation and optional visible hold |
| MCP tool | `trigger_recall_opt_in_enforce_hold` | explicit opt-in response contract |

The default `memory_search` tool must remain a bare hit-list search with no
implicit policy hold.

## Required Modes

| Mode | Store Search | Visible Hits | Meaning |
|---|---|---|---|
| `off` | no wrapper behavior | baseline/default path | current behavior |
| `audit_only` | only when requested for counts or accepted hits | baseline hits remain visible | reports `would_hold` without suppression |
| `pre_policy_hold` | no store search for held queries unless `include_baseline_counts=true` | explicit held packet | production-shaped hold without baseline telemetry |
| `enforce_hold` | no store search for held queries unless explicitly count-audited | explicit held packet | production visible hold, future approval only |

The first implementation slice after this proposal, if later approved, should
stop at `audit_only` or `pre_policy_hold` simulation. `enforce_hold` should be a
separate follow-up.

## Pre-Policy Semantics

For a candidate production hold path, query intent must run before baseline
store search.

Required behavior for rejected query intent:

1. classify query intent;
2. return a held packet with an explicit reason;
3. do not call store FTS by default;
4. do not call MCP `memory_search`;
5. do not record coactivation or access traces for withheld hits;
6. report `baseline_count_status=not_requested_pre_policy_hold`;
7. call store FTS only when an explicitly count-audited mode requests baseline
   counts, and mark that as audit evidence rather than normal production
   behavior.

Required behavior for accepted query intent:

1. call the same baseline FTS path used by the gated baseline trial;
2. preserve baseline order;
3. return only redacted audit metadata plus visible hits allowed by the
   response contract;
4. record any access/coactivation side effects only for hits actually returned,
   and only if the surrounding store path already does so.

## Response Contract

Future implementation should return an object, not a bare array:

```json
{
  "schema": "agent_bridge.memory.trigger_recall.enforce_hold_opt_in.v0",
  "read_only": false,
  "mode": "pre_policy_hold",
  "status": "held_by_query_intent",
  "default_memory_search_unchanged": true,
  "changes_this_opt_in_call": true,
  "hits": [],
  "query_intent": {
    "decision": "hold",
    "reject_reason": "frontend_dashboard_intent"
  },
  "baseline": {
    "memory_search_called": false,
    "baseline_count_status": "not_requested_pre_policy_hold",
    "baseline_candidate_count": null
  },
  "audit": {
    "query_hash": "sha256:...",
    "regression_anchor": "aio2_trigger_recall_baseline_acceptance_shadow_20260623",
    "raw_query_included": false,
    "raw_keys_included": false,
    "content_included": false
  }
}
```

The response must distinguish:

- `returned_accepted`: accepted query, baseline hits visible;
- `would_hold`: audit-only hold, baseline behavior not suppressed;
- `held_by_query_intent`: visible opt-in hold with explicit reason;
- `blocked_to_baseline`: authorization missing, wrapper failed open;
- `operator_disabled`: operator kill switch active, wrapper failed open;
- `baseline_search_error`: accepted query needed baseline search but search
  failed.

## Authorization Gates

All gates must pass before `enforce_hold` can affect visible results:

| Gate | Required State |
|---|---|
| operator approval packet | present, current, redacted, board-visible |
| reviewer | explicit non-empty reviewer identity |
| implementation commit | exact commit under review |
| regression anchor | `aio2_trigger_recall_baseline_acceptance_shadow_20260623` |
| batch diagnostics | `ready_for_enforce_hold_review_packet` evidence present |
| mode | `fts` only |
| scope | exact `project:/...` local project scope |
| scope mode | `local_only` |
| per-call opt-in | true on every call |
| runtime env | proposed `AB_TRIGGER_RECALL_ENFORCE_HOLD_OPT_IN=1` |
| operator disable env | proposed `AB_TRIGGER_RECALL_ENFORCE_HOLD_DISABLE` absent/false |
| response shape | object response, never bare empty array for held queries |
| raw fields | raw query/key/content absent from audit output |

If any gate fails, the wrapper must fail open to baseline behavior and report
blockers. It must not partially enforce a hold.

## Approval Packet Minimum

A future approval packet must include:

- approving reviewer and author;
- exact implementation commit;
- forum post id;
- memory key;
- regression command results;
- batch diagnostics packet hash or summary;
- explicit statement that default `memory_search` remains unchanged;
- explicit statement whether the approved slice is `audit_only`,
  `pre_policy_hold`, or `enforce_hold`;
- rollback command or feature-flag disable path;
- expiry or freshness policy.

No forum post or memory note should be treated as approval unless it names the
mode and exact commit.

## Test Gate Before Any Implementation

Required before an implementation PR or commit is accepted:

```bash
cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
cargo test -p ab-bridge --example trigger_recall_eval -- --nocapture
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
cargo check -p ab-bridge --lib
git diff --check
```

Required result thresholds:

| Metric | Required |
|---|---:|
| true hits lost by shadow gate | 0 |
| positive cases held | 0 |
| baseline false hits after shadow gate | 0 |
| accepted gated trial order drift | 0 |
| held responses as bare empty arrays | 0 |
| raw query/key/content leaks | 0 |

If any positive case becomes held, implementation must stop at `audit_only`.

## Rollback Boundary

The first implementation must have a single operator kill switch. Proposed:

```text
AB_TRIGGER_RECALL_ENFORCE_HOLD_DISABLE=1
```

When active, the wrapper must:

- fail open to baseline behavior;
- report `operator_disabled`;
- not enforce visible hold;
- not change default `memory_search`;
- not mutate memory or graph state.

## Non-Goals

This proposal does not authorize:

- editing default `memory_search`;
- hidden parameters on default `memory_search`;
- production enforcement in `hybrid` or `semantic` mode;
- returning `[]` for held queries without a held status object;
- ranking changes for accepted baseline hits;
- tokenizer/schema/indexing/reindex changes;
- graph or semantic expansion;
- coactivation evidence for withheld hits;
- memory writes;
- graph-edge writes;
- auto-approval based only on eval metrics.

## Recommended Next Step

Closed by
`docs/reports/goal-c-u/2026-06-23-trigger-recall-pre-policy-hold-approval-packet-schema.md`.

Next safe action: review that schema or propose an implementation plan that
names exact files and tests while still stopping at `pre_policy_hold_simulation`.
Do not implement production `enforce_hold` until a later approval packet names
the exact implementation commit.
