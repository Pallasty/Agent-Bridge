# Workflow Feedback Co-Surface Latch Usage Evidence

Date: 2026-07-01

Status: `DOCS_ONLY_USAGE_EVIDENCE / READ_ONLY_SHADOW_SCORE / NO_RUNTIME_CHANGE`

## Decision

The workflow-feedback runbook remains useful on newly completed Agent-Bridge
lanes when the lesson is concrete, falsifiable, and kept out of runtime
influence.

This slice packages two fresh Experience Object fixtures:

- correction co-surface S1 evidence, already present on current `HEAD`;
- bounded coactivation latch stale-gate cleanup evidence, added with this
  packet.

The run scored both held-out scenarios twice, generated an owner-review packet,
and generated a low-risk promotion record for documentation, durable-memory,
and runbook use only. It does not write memory, change retrieval ranking, alter
tool routing, mutate runtime policy, restart daemons, deploy, or enable
`AGENT_BRIDGE_CORRECTION_COSURFACE` in any long-lived process.

## Source Anchors

- `docs/design/fixtures/workflow-feedback-experience-correction-cosurface-s1-2026-07-01.json`
- `docs/design/fixtures/workflow-feedback-experience-bounded-latch-gate-cleanup-2026-07-01.json`
- `docs/design/fixtures/workflow-feedback-shadow-score-scenarios-2026-07-01-cosurface-latch.json`
- `docs/design/fixtures/workflow-feedback-baseline-observations-2026-07-01-cosurface-latch.json`
- `docs/reports/goal-c-u/2026-07-01-correction-cosurface-s1-closeout.md`
- `docs/reports/goal-c-u/2026-07-01-bounded-coactivation-latch-current-state.md`
- `docs/reports/goal-c-u/2026-07-01-active-workmemory-board-staleness-audit.md`
- current correction fixture commit:
  `c1099fe docs(workflow): add cosurface experience fixture`

## New Fixture Read

The bounded-latch fixture captures this reusable lesson:

> When a board or design doc says owner-gated/not implemented, verify against
> source, tests, live schema, and durable memory before planning
> implementation. Stale gate text should be corrected as queue hygiene, not
> obeyed as a current blocker.

The correction co-surface fixture captures this reusable lesson:

> For gated retrieval read-path changes, separate copied-DB tool-path proof,
> short-lived live child-process proof, and long-lived runtime windows.
> Standing reversible authorization can cover S1 when rollback is process
> termination plus env verification, but it should not collapse into S2.

Both fixtures keep future influence disabled:

```json
{
  "fixture_writes_memory": false,
  "fixture_changes_runtime": false,
  "fixture_changes_retrieval_order": false,
  "fixture_authorizes_future_runtime_influence": false
}
```

## Shadow-Score Replay

Command:

```text
agent-bridge workflow-feedback-shadow-score \
  --fixture docs/design/fixtures/workflow-feedback-experience-correction-cosurface-s1-2026-07-01.json \
  --fixture docs/design/fixtures/workflow-feedback-experience-bounded-latch-gate-cleanup-2026-07-01.json \
  --scenario "A future Agent-Bridge session has AGENT_BRIDGE_CORRECTION_COSURFACE evidence from copied DB and S1 child-process trials, and asks whether to run S2 daemon enablement or keep long-lived processes disabled." \
  --scenario "A future queue audit finds a design document saying bounded coactivation latch is owner-gated and not implemented, but source shows v38 last_cofire_at and max_latched_edges tests already landed." \
  --json > /tmp/workflow-feedback-cosurface-latch-shadow-run-1.json
```

The same command was repeated for:

```text
/tmp/workflow-feedback-cosurface-latch-shadow-run-2.json
```

Both runs produced identical rankings:

| Scenario | Rank | Experience | Shadow score | Readiness | Relevance | Verdict |
|---|---:|---|---:|---:|---:|---|
| correction co-surface S1 or S2 decision | 1 | `exp_20260701_correction_cosurface_s1_keep_disabled` | 72 | 100 | 57 | `likely_helpful_shadow_candidate` |
| correction co-surface S1 or S2 decision | 2 | `exp_20260701_bounded_latch_stale_gate_cleanup` | 44 | 100 | 14 | `weak_match_needs_review` |
| bounded latch stale gate text | 1 | `exp_20260701_bounded_latch_stale_gate_cleanup` | 71 | 100 | 55 | `likely_helpful_shadow_candidate` |
| bounded latch stale gate text | 2 | `exp_20260701_correction_cosurface_s1_keep_disabled` | 50 | 100 | 23 | `possible_shadow_candidate` |

The shadow-score boundary remained:

```json
{
  "writes_memory": false,
  "changes_retrieval_order": false,
  "mutates_runtime_policy": false,
  "runtime_influence_allowed": false,
  "owner_gated_runtime_influence": true
}
```

## Owner-Review Packet

Command:

```text
agent-bridge workflow-feedback-owner-review-packet \
  --scenario-fixture docs/design/fixtures/workflow-feedback-shadow-score-scenarios-2026-07-01-cosurface-latch.json \
  --baseline-observation docs/design/fixtures/workflow-feedback-baseline-observations-2026-07-01-cosurface-latch.json \
  --shadow-score /tmp/workflow-feedback-cosurface-latch-shadow-run-1.json \
  --shadow-score /tmp/workflow-feedback-cosurface-latch-shadow-run-2.json \
  --rollback-ref "rollback:archive or remove 2026-07-01 workflow-feedback cosurface/latch fixtures and keep runtime influence disabled" \
  --json > /tmp/workflow-feedback-cosurface-latch-owner-review-packet.json
```

Result:

```text
schema=agent_bridge.workflow_feedback_owner_review_packet.v0
owner_review_verdict=ready_for_owner_review
ready_for_owner_review=true
advisory_promotion_ready=false
```

Checks:

| Check | Passed | Evidence |
|---|---|---|
| `baseline_evidence_ready` | true | `baseline_evidence_ready` |
| `measured_lift_anchor` | true | `measured_lift_anchor` |
| `promotion_gate_ready_for_owner_review` | true | `ready_for_owner_review` |
| `owner_approval_present` | false | `0 owner approval ref(s)` |

The missing owner approval is expected in the owner-review packet itself. This
packet is review evidence, not a promotion application.

## Promotion Record

Command:

```text
agent-bridge workflow-feedback-promotion-record \
  --owner-review-packet /tmp/workflow-feedback-cosurface-latch-owner-review-packet.json \
  --promotion-scope documentation \
  --promotion-scope durable_memory \
  --promotion-scope runbook \
  --owner-approval-ref "user:2026-07-01 standing reversible authorization; low-risk documentation, durable-memory, and runbook evidence only" \
  --rollback-ref "rollback:archive or remove 2026-07-01 workflow-feedback cosurface/latch fixtures and supersede durable memory" \
  --json > /tmp/workflow-feedback-cosurface-latch-promotion-record.json
```

Result:

```text
schema=agent_bridge.workflow_feedback_promotion_record.v0
promotion_record_verdict=docs_memory_runbook_promotion_record_ready
promotion_record_ready=true
```

Accepted scopes:

| Scope | Accepted | Reason |
|---|---|---|
| documentation | true | Documentation-only promotion is reversible and does not alter runtime behavior. |
| durable_memory | true | Durable memory promotion is allowed only as an explicit `memory_save` in a later step. |
| runbook | true | Runbook promotion is advisory documentation and keeps runtime influence disabled. |

No blocked scopes were requested. The promotion record still keeps:

```json
{
  "writes_memory": false,
  "changes_retrieval_order": false,
  "mutates_runtime_policy": false,
  "runtime_influence_allowed": false
}
```

## Read

This run strengthens four narrow claims:

1. The workflow-feedback runbook can generalize from the original 2026-06-30
   fixtures to newly completed 2026-07-01 work.
2. The two held-out scenarios retrieved the intended Experience Object first in
   two repeated shadow-score runs.
3. Baseline proxy evidence remained explicit: previous policy selected no
   relevant experience for either scenario, while shadow-score matched 4 of 4
   top candidates.
4. The standing reversible authorization is sufficient for low-risk
   documentation, durable-memory, and runbook evidence promotion, but it does
   not authorize runtime influence.

It does not prove production behavior lift. It is evidence that the review
workflow is repeatable and that these two lessons are now packaged for future
human-reviewed use.

## Non-Authorizations

This report does not authorize:

- live memory DB writes beyond a separate explicit durable-memory save step;
- retrieval ranking changes;
- default `memory_search` behavior changes;
- tool routing changes;
- runtime-policy changes;
- prompt, profile, bootstrap, skill, or MCP-profile changes;
- default or long-lived `AGENT_BRIDGE_CORRECTION_COSURFACE` enablement;
- S2 daemon or active-client windows;
- daemon restart or deploy.

## Recommended Next Step

Save one durable memory summarizing this packet, then post the result to the
workflow-feedback forum thread. Keep the next implementation lane on queue
hygiene and read-only evidence unless a separate runtime-influence review is
opened.
