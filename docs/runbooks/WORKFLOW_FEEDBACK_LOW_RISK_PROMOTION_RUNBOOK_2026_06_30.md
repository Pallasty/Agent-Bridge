# Workflow Feedback Low-Risk Promotion Runbook

Date: 2026-06-30
Scope: documentation, durable memory, and runbook promotion only
Status: applied low-risk promotion record

## Decision

The workflow-feedback evidence chain is promoted into a reusable documentation
and runbook workflow.

This promotion does not authorize retrieval ranking changes, tool-routing
changes, runtime-policy changes, prompt/profile/bootstrap mutation, skill
creation, skill installation, or default influence.

## Approval And Boundary

Approval ref:

```text
user:2026-06-30 current thread: proceed according to Codex judgment; limited to documentation, durable-memory, and runbook promotion
```

Rollback ref:

```text
rollback: remove this runbook/doc update and archive the durable memory key
```

The approval is interpreted narrowly. It allows the completed workflow-feedback
evidence chain to become a repeatable human-review workflow. It does not grant
permission to alter live Agent-Bridge behavior.

## When To Use This Runbook

Use this runbook when a completed Agent-Bridge workflow lesson might be worth
reusing across future sessions.

Good candidates have:

- a concrete completed workflow episode;
- one or more Experience Object fixtures;
- held-out scenarios;
- repeated shadow scoring;
- baseline evidence;
- measured lift evidence;
- rollback evidence;
- owner-review packet status.

Do not use this runbook to justify default runtime influence. Runtime,
retrieval, tool-routing, prompt, profile, bootstrap, and skill changes need a
separate stronger authorization lane.

## Evidence Chain

The accepted low-risk evidence chain is:

1. `workflow-feedback-report`
2. Experience Object fixtures
3. `workflow-feedback-shadow-score`
4. `workflow-feedback-promotion-gate`
5. `workflow-feedback-lift-evidence`
6. `workflow-feedback-baseline-evidence`
7. `workflow-feedback-owner-review-packet`
8. `workflow-feedback-promotion-record`

Canonical design document:

- `docs/design/WORKFLOW_FEEDBACK_LOOP_RESEARCH_2026_06_30.md`

Canonical fixtures:

- `docs/design/fixtures/workflow-feedback-experience-agent-send-input-2026-06-30.json`
- `docs/design/fixtures/workflow-feedback-experience-report-cli-2026-06-30.json`
- `docs/design/fixtures/workflow-feedback-shadow-score-scenarios-2026-06-30.json`
- `docs/design/fixtures/workflow-feedback-promotion-gate-evidence-2026-06-30.json`
- `docs/design/fixtures/workflow-feedback-lift-evidence-anchor-2026-06-30.json`
- `docs/design/fixtures/workflow-feedback-baseline-observations-2026-06-30.json`
- `docs/design/fixtures/workflow-feedback-owner-review-packet-2026-06-30.json`
- `docs/design/fixtures/workflow-feedback-promotion-record-2026-06-30.json`

## Reproduce The Current Packet

Generate two independent shadow-score packets:

```text
agent-bridge workflow-feedback-shadow-score \
  --fixture docs/design/fixtures/workflow-feedback-experience-agent-send-input-2026-06-30.json \
  --fixture docs/design/fixtures/workflow-feedback-experience-report-cli-2026-06-30.json \
  --scenario "<held-out scenario A>" \
  --scenario "<held-out scenario B>" \
  --json > /tmp/workflow-feedback-shadow-score-run-1.json
```

Repeat the same command for:

```text
/tmp/workflow-feedback-shadow-score-run-2.json
```

Assemble the owner-review packet:

```text
agent-bridge workflow-feedback-owner-review-packet \
  --scenario-fixture docs/design/fixtures/workflow-feedback-shadow-score-scenarios-2026-06-30.json \
  --baseline-observation docs/design/fixtures/workflow-feedback-baseline-observations-2026-06-30.json \
  --shadow-score /tmp/workflow-feedback-shadow-score-run-1.json \
  --shadow-score /tmp/workflow-feedback-shadow-score-run-2.json \
  --rollback-ref "rollback:remove workflow feedback promoted artifact and keep runtime influence disabled" \
  --json > /tmp/workflow-feedback-owner-review-packet.json
```

Create the low-risk promotion record:

```text
agent-bridge workflow-feedback-promotion-record \
  --owner-review-packet /tmp/workflow-feedback-owner-review-packet.json \
  --promotion-scope documentation \
  --promotion-scope durable_memory \
  --promotion-scope runbook \
  --owner-approval-ref "user:2026-06-30 current thread: proceed according to Codex judgment; limited to documentation, durable-memory, and runbook promotion" \
  --rollback-ref "rollback:remove this runbook/doc update and archive the durable memory key" \
  --json
```

Expected verdict:

```text
docs_memory_runbook_promotion_record_ready
```

## Durable Memory Save Template

When applying the low-risk promotion, save a durable memory with:

```text
key: workflow_feedback_low_risk_promotion_applied_20260630
kind: decision
scope: project:/Data/CascadeProjects/agent-bridge
tags: workflow-feedback, runbook, durable-memory, low-risk-promotion, owner-gated
```

The memory must include:

- approval ref;
- rollback ref;
- branch and commit that applied the runbook;
- validation commands;
- explicit non-goals.

## Rollback

Rollback is documentation-only:

1. Revert or supersede this runbook.
2. Revert the Slice 10 design-doc update.
3. Archive or supersede `workflow_feedback_low_risk_promotion_applied_20260630`.

Rollback does not require runtime shutdown because this runbook does not change
runtime behavior.

## Blocked Scopes

The following remain blocked unless a stronger separate lane authorizes them:

- skill creation or installation;
- retrieval ranking or default `memory_search` behavior;
- tool routing;
- runtime policy;
- prompts;
- profiles;
- bootstrap;
- MCP-visible default influence.

## Falsifier

If future workflow-feedback lessons using this runbook fail to produce cleaner
handoffs, faster recovery, or fewer repeated planning loops, keep the runbook as
historical documentation and redesign the evidence chain before promoting more
lessons.
