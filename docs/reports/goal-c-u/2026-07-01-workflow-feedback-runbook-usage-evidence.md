# Workflow Feedback Runbook Usage Evidence

Date: 2026-07-01

Status: `DOCS_ONLY_USAGE_EVIDENCE / READ_ONLY_REPLAY / NO_RUNTIME_CHANGE`

## Decision

The workflow-feedback low-risk promotion runbook remains usable as a repeatable
read-only review workflow.

This slice replayed the current report, shadow-score, owner-review packet, and
promotion-record commands. The replay supports continued documentation,
durable-memory, and runbook usage. It does not authorize retrieval ranking,
tool-routing, runtime-policy, prompt/profile/bootstrap, skill, MCP-profile, or
default memory-search changes.

## Source Anchors

- `docs/runbooks/WORKFLOW_FEEDBACK_LOW_RISK_PROMOTION_RUNBOOK_2026_06_30.md`
- `docs/design/WORKFLOW_FEEDBACK_LOOP_RESEARCH_2026_06_30.md`
- `docs/reports/goal-c-u/2026-06-30-workflow-feedback-report.md`
- `docs/reports/goal-c-u/2026-07-01-agent-bridge-open-queue-staleness-audit.md`
- fixture set under `docs/design/fixtures/workflow-feedback-*.json`

## Current Report Replay

Command:

```text
agent-bridge workflow-feedback-report --json \
  > /tmp/workflow-feedback-report-usage-20260701.json
```

Selected current evidence:

| Metric | Value |
|---|---:|
| active memories | 670 |
| feedback rows | 7 |
| feedback fraction | 1.0% |
| memory graph edges | 1875 |
| observed tools | 32 |
| 24h MCP calls in report window | 691 |
| 24h MCP errors in report window | 14 |
| error rate | 2.0% |

Current scorecard read:

| Axis | Status | Evidence |
|---|---|---|
| Capture coverage | partial | 670 active memories and 691 MCP calls in the selected window |
| Attribution quality | partial | 1875 memory graph edges and 32 observed tools |
| Feedback density | low | 7 feedback rows out of 670 active rows |
| Retrieval influence | conservative | report observes feedback but does not alter bootstrap, ranking, or routing |
| Behavior lift | measurable | 691 calls, 14 errors, 2.0% error rate |
| Governance | strong | read-only report, runtime influence disabled, owner gate required |

The report boundary remained:

```json
{
  "writes_memory": false,
  "changes_retrieval_order": false,
  "mutates_runtime_policy": false,
  "runtime_influence_allowed": false,
  "owner_gated_runtime_influence": true
}
```

## Shadow-Score Replay

Commands:

```text
agent-bridge workflow-feedback-shadow-score \
  --fixture docs/design/fixtures/workflow-feedback-experience-agent-send-input-2026-06-30.json \
  --fixture docs/design/fixtures/workflow-feedback-experience-report-cli-2026-06-30.json \
  --scenario "A future Agent-Bridge session finds that interactive Claude Code accepts no follow-up agent_send_input after reconnect because the child process is blocked on a chrome/browser first-run prompt." \
  --scenario "A future planning session asks whether workflow-feedback lessons should immediately change retrieval ranking or tool routing, or remain report-first with shadow scoring and owner gates." \
  --json > /tmp/workflow-feedback-shadow-score-usage-20260701-run-1.json
```

The same command was repeated for:

```text
/tmp/workflow-feedback-shadow-score-usage-20260701-run-2.json
```

Both independent runs produced the expected top-ranked experience for both
held-out scenarios:

| Scenario | Expected top | Observed top | Shadow score |
|---|---|---|---:|
| interactive `agent_send_input` first-run stall | `exp_20260630_agent_send_input_no_chrome` | `exp_20260630_agent_send_input_no_chrome` | 69 |
| workflow-feedback policy pressure | `exp_20260630_workflow_feedback_report_cli` | `exp_20260630_workflow_feedback_report_cli` | 71 |

Each shadow-score report remained read-only with:

```json
{
  "candidate_count": 2,
  "writes_memory": false,
  "changes_retrieval_order": false,
  "mutates_runtime_policy": false,
  "runtime_influence_allowed": false
}
```

## Owner-Review Packet Replay

Command:

```text
agent-bridge workflow-feedback-owner-review-packet \
  --scenario-fixture docs/design/fixtures/workflow-feedback-shadow-score-scenarios-2026-06-30.json \
  --baseline-observation docs/design/fixtures/workflow-feedback-baseline-observations-2026-06-30.json \
  --shadow-score /tmp/workflow-feedback-shadow-score-usage-20260701-run-1.json \
  --shadow-score /tmp/workflow-feedback-shadow-score-usage-20260701-run-2.json \
  --rollback-ref "rollback:remove workflow feedback promoted artifact and keep runtime influence disabled" \
  --json > /tmp/workflow-feedback-owner-review-packet-usage-20260701.json
```

Checks:

| Check | Passed | Evidence |
|---|---|---|
| `baseline_evidence_ready` | true | `baseline_evidence_ready` |
| `measured_lift_anchor` | true | `measured_lift_anchor` |
| `promotion_gate_ready_for_owner_review` | true | `ready_for_owner_review` |
| `owner_approval_present` | false | `0 owner approval ref(s)` |

The failed `owner_approval_present` check is expected for this replay. This
slice intentionally did not create a new owner approval ref and did not apply
any higher-blast promotion.

Recommended packet actions remained:

- send the packet for explicit owner approval with baseline, metric-anchor, and
  rollback refs attached;
- do not apply any promotion until an owner approval ref is recorded.

## Promotion-Record Replay

Command:

```text
agent-bridge workflow-feedback-promotion-record \
  --owner-review-packet /tmp/workflow-feedback-owner-review-packet-usage-20260701.json \
  --promotion-scope documentation \
  --promotion-scope durable_memory \
  --promotion-scope runbook \
  --owner-approval-ref "user:2026-06-30 current thread: proceed according to Codex judgment; limited to documentation, durable-memory, and runbook promotion" \
  --rollback-ref "rollback:remove this runbook/doc update and archive the durable memory key" \
  --json > /tmp/workflow-feedback-promotion-record-usage-20260701.json
```

Result:

```text
promotion_record_verdict=docs_memory_runbook_promotion_record_ready
```

No blocked scopes were requested in this replay. The record still recommends
only a small follow-up for documentation, durable-memory, or runbook promotion,
carrying the approval and rollback refs forward.

## Read

This replay strengthens three narrow claims:

1. The runbook commands still execute successfully on current `master`.
2. The held-out scenarios still rank the expected Experience Object fixture
   first in repeated shadow-score runs.
3. The promotion path remains explicitly low-risk and owner-gated.

It does not prove runtime behavior lift. Feedback density is still low at 7
feedback rows out of 670 active memories, so workflow-feedback should remain a
measurement and review loop rather than a default optimization signal.

## Non-Authorizations

This report does not authorize:

- live memory DB writes;
- new durable memory writes beyond a separate explicit save step;
- runtime policy changes;
- retrieval ranking changes;
- default `memory_search` behavior changes;
- tool routing changes;
- prompt, profile, or bootstrap changes;
- skill creation or installation;
- daemon restart;
- deploy;
- owner-gated co-surface A/B enablement.

## Recommended Next Step

Use this replay as the first post-promotion usage evidence for the workflow
feedback runbook. If this pattern repeats successfully on future completed
lanes, collect comparable reports and only then consider a separate owner
review packet for broader influence. Until then, keep workflow feedback in the
documentation, durable-memory, and runbook lane.
