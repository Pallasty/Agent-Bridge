# Workflow Feedback Correction Co-Surface Experience Evidence

Date: 2026-07-01

Status: `DOCS_ONLY_FIXTURE_EVIDENCE / READ_ONLY_SHADOW_SCORE / NO_RUNTIME_CHANGE`

## Decision

Promote the completed correction co-surface S1 lane into workflow-feedback
evidence as a manually reviewed Experience Object fixture.

This slice adds one fixture and one held-out scenario, then runs the existing
read-only `workflow-feedback-shadow-score` CLI twice. It does not write memory,
change retrieval ranking, mutate runtime policy, change tool routing, restart
daemons, deploy, or enable `AGENT_BRIDGE_CORRECTION_COSURFACE` in any long-lived
process.

## Source Anchors

- `docs/reports/goal-c-u/2026-07-01-correction-cosurface-s1-closeout.md`
- `docs/reports/goal-c-u/2026-07-01-correction-cosurface-ab-enablement-packet.md`
- `docs/reports/goal-c-u/2026-07-01-correction-cosurface-mcp-ab-smoke.md`
- durable memory `correction_cosurface_s1_closeout_20260701`
- forum thread #102 posts #2763, #2766, #2770, #2773, and #2774
- final correction co-surface closeout head:
  `dd88a74 docs(memory): correct cosurface s1 postcheck`

New artifacts:

- `docs/design/fixtures/workflow-feedback-experience-correction-cosurface-s1-2026-07-01.json`
- `docs/design/fixtures/workflow-feedback-shadow-score-scenarios-correction-cosurface-2026-07-01.json`

## Fixture Read

The new Experience Object captures this reusable workflow lesson:

> For gated retrieval behavior, split evidence into copied-store smoke,
> short-lived child-process trial, and long-lived runtime window. Backup first,
> keep the env flag process-scoped, verify rollback by process termination and
> env scan, and do not let a targeted pass become default enablement.

Key evidence encoded in the fixture:

| Evidence | Value |
|---|---|
| S0.5 copied-DB MCP smoke | passed |
| S1 live-store short-lived subprocess trial | passed |
| backup sha256 | `984516adeb577ea6e10c667281e1790287cf093b3d3f736a7318d7f223a3a817` |
| final head | `dd88a74` |
| long-lived co-surface flag | disabled / absent |
| S2/default enablement | not warranted |

The fixture safety flags are all false:

```json
{
  "fixture_writes_memory": false,
  "fixture_changes_runtime": false,
  "fixture_changes_retrieval_order": false,
  "fixture_authorizes_future_runtime_influence": false
}
```

## Calibration Note

The first draft scenario was too broad. It tied the new correction fixture with
the older generic workflow-feedback report fixture at score `55`, and the older
fixture sorted first. That was a useful failure: a scenario about gated
retrieval experiments must name the concrete discriminators that make this
experience reusable.

The scenario was narrowed to include:

- correction co-surface behavior;
- subprocess env trial;
- backup;
- `exclude_kinds`;
- limit checks;
- rollback env scan;
- long-lived flag disabled;
- no S2 daemon window.

After that calibration, both independent runs ranked the new correction fixture
first.

## Shadow-Score Replay

Command shape:

```text
/home/pallasting/.local/bin/agent-bridge.real workflow-feedback-shadow-score \
  --fixture docs/design/fixtures/workflow-feedback-experience-agent-send-input-2026-06-30.json \
  --fixture docs/design/fixtures/workflow-feedback-experience-report-cli-2026-06-30.json \
  --fixture docs/design/fixtures/workflow-feedback-experience-correction-cosurface-s1-2026-07-01.json \
  --scenario "<correction co-surface held-out scenario>" \
  --json
```

Outputs:

- `/tmp/workflow-feedback-cosurface-shadow-score-20260701-run-1.json`
- `/tmp/workflow-feedback-cosurface-shadow-score-20260701-run-2.json`

Both runs:

```text
schema=agent_bridge.workflow_feedback_shadow_score.v0
read_only=true
candidate_count=3
top_experience_id=exp_20260701_correction_cosurface_s1_pass
top_score=66
top_relevance=48
top_verdict=likely_helpful_shadow_candidate
writes_memory=false
changes_retrieval_order=false
mutates_runtime_policy=false
runtime_influence_allowed=false
```

Ranking was stable:

| Rank | Experience | Score | Relevance | Matched terms |
|---:|---|---:|---:|---|
| 1 | `exp_20260701_correction_cosurface_s1_pass` | 66 | 48 | `backup`, `correction`, `daemon`, `disabled`, `env`, `exclude_kinds`, `flag` |
| 2 | `exp_20260630_workflow_feedback_report_cli` | 53 | 28 | `behavior`, `bridge`, `surface`, `window` |
| 3 | `exp_20260630_agent_send_input_no_chrome` | 51 | 24 | `behavior`, `bridge`, `session`, `surface` |

## Read

This is positive evidence for the workflow-feedback runbook:

1. A completed Agent-Bridge lane could be converted into a structured
   Experience Object without changing runtime.
2. A held-out scenario about future gated retrieval experiments retrieved the
   intended experience after scenario wording was calibrated.
3. The calibration failure was visible and fixable in the artifact itself,
   instead of being hidden behind a runtime policy change.
4. The result supports continued docs/durable-memory/runbook use, not broader
   default influence.

## Non-Authorizations

This report does not authorize:

- default `AGENT_BRIDGE_CORRECTION_COSURFACE` enablement;
- S2 daemon or active-client windows;
- retrieval ranking changes;
- tool-routing changes;
- runtime-policy changes;
- prompt, profile, bootstrap, or MCP-profile changes;
- skill creation or installation;
- memory writes beyond a separate explicit durable-memory save step;
- daemon restart or deploy.

## Recommended Next Step

Keep collecting Experience Object fixtures from completed lanes where the
lesson is concrete and falsifiable. The next high-value workflow-feedback task
is not runtime influence; it is a small comparison set of 3-5 fixtures plus
held-out scenarios that reveal when scenarios are too broad, too generic, or
actually discriminative.
