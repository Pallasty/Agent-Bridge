# Workflow Feedback Loop Research for Agent-Bridge

Date: 2026-06-30

Role: research synthesis / docs-only planning anchor

Persistence anchors:

- Memory: `workflow_feedback_loop_research_20260630`
- Forum: thread `#108`, post `#2658`

This note records the external research pass for Agent-Bridge as a workflow
feedback system. The operating question is:

> How can Agent-Bridge accumulate feedback from Codex/agent work loops so later
> sessions improve workflow quality, tool-call accuracy, and tool-use
> efficiency?

## Position

Agent-Bridge is already beyond a plain memory store. It has the foundations of
an observable workflow-feedback substrate:

- durable memory and graph edges
- session bootstrap recall
- work memory for active lanes
- forum coordination
- MCP/tool-call telemetry
- lifecycle/readiness reporting
- memory retrieval feedback and correction feedback
- consolidation queues and shadow evaluation patterns

The current maturity is best described as:

- L3/L4: mature enough for cross-session continuity and shared coordination.
- L5: mid to late stage. Feedback can be captured and reviewed, but is still
  mostly advisory and manually interpreted.
- L6: early stage. There are shadow-evaluation and influence-gate patterns, but
  no stable automatic optimizer for workflow policy.
- L7: not closed. Agent-Bridge should not yet self-change runtime policy from
  feedback without owner review, falsifiers, and rollback evidence.

The next useful move is not reinforcement learning or automatic policy mutation.
It is to close a measurable loop:

```text
work trajectory -> outcome label -> reflection -> reusable lesson/skill ->
later retrieval/influence -> measured behavior lift
```

## External Research Anchors

These projects and papers offer patterns that Agent-Bridge can borrow without
copying their whole architecture.

### Reflexion

Anchor: <https://arxiv.org/abs/2303.11366>

Reflexion turns task feedback into verbal reflections stored as episodic memory.
The useful borrowing is the loop shape: failure or success should produce a
compact natural-language lesson that later attempts can retrieve. For
Agent-Bridge, this maps to verified outcome records plus durable memories tagged
by trigger conditions.

### Self-Refine

Anchor: <https://arxiv.org/abs/2303.17651>

Self-Refine separates generation, feedback, and refinement. The borrowing is
not the exact prompt pattern; it is the separation of roles. Agent-Bridge should
keep raw trace, critique/reflection, and revised policy/lesson as distinct
records so later agents can audit whether a lesson was justified.

### ExpeL

Anchor: <https://arxiv.org/abs/2308.10144>

ExpeL maintains an experience pool and uses accumulated experience to improve
future task solving. Agent-Bridge can adapt this as an "experience object"
library that stores reusable workflow episodes rather than isolated memory
notes.

### Voyager

Anchor: <https://arxiv.org/abs/2305.16291>

Voyager combines automatic curriculum, execution feedback, and a skill library.
The useful borrowing is skill crystallization: repeated successful trajectories
should become named workflows or runbooks, while failures should become
falsifiers and guardrails.

### MemGPT / Letta

Anchor: <https://arxiv.org/abs/2310.08560>

MemGPT focuses on long-term memory management for agents. The borrowing is
memory governance: Agent-Bridge should distinguish immediate context, active
scratchpad, durable memory, and archival evidence instead of flattening all
feedback into one recall surface.

### Mem0, Zep/Graphiti, A-MEM

Anchors:

- <https://github.com/mem0ai/mem0>
- <https://github.com/getzep/graphiti>
- <https://arxiv.org/abs/2502.12110>

These systems emphasize structured memory, graph/temporal context, and agentic
memory updates. The useful borrowing is temporal graph discipline: feedback
should be linked to task, tool, source, outcome, and later use, not only stored
as text.

### DSPy

Anchor: <https://arxiv.org/abs/2310.03714>

DSPy optimizes LM pipelines against metrics. The borrowing is metric-first
optimization: before changing AB behavior, define held-out tasks and score
whether retrieval, planning, or tool choice improved.

### TextGrad

Anchor: <https://arxiv.org/abs/2406.07496>

TextGrad treats textual feedback as an optimization signal. The borrowing is
the idea of "textual gradients" for workflow components: failed tool calls,
stale memories, and missed context can produce targeted natural-language
suggestions, but AB should apply them through reviewable shadow proposals first.

### Agent Lightning

Anchor:
<https://www.microsoft.com/en-us/research/blog/agent-lightning-adding-reinforcement-learning-to-ai-agents-without-code-rewrites/>

Agent Lightning frames agent trajectories as state/action/reward data that can
train policies without rewriting the agent. The borrowing is the trajectory
schema and decoupling pattern. Agent-Bridge should first normalize work-loop
episodes into state/action/observation/outcome records. Actual RL is a later
option, not a near-term default.

### Observability Stacks

Anchors:

- <https://arize.com/docs/phoenix>
- <https://langfuse.com/docs>
- <https://opentelemetry.io/docs/specs/semconv/>

Phoenix/OpenInference, Langfuse, and OpenTelemetry GenAI conventions point to
the same lesson: workflow feedback becomes useful only when traces have stable
span boundaries and consistent attributes. Agent-Bridge should standardize
task, plan, tool, verification, and outcome spans before optimizing behavior.

## Agent-Bridge Borrowing Model

The external systems suggest a conservative AB-specific stack:

1. Trace the work loop.
2. Label the outcome.
3. Reflect into a compact lesson.
4. Link lesson to source trajectory and later retrieval.
5. Promote repeated successful lessons into skills/runbooks.
6. Run policy changes in shadow mode.
7. Require owner-gated influence before runtime/default behavior changes.

This preserves the current AB design principle: self-improvement is valuable
only when observable, falsifiable, reversible, and not silently self-authorized.

## Experience Object v0

Agent-Bridge should introduce a normalized experience object before adding any
new optimizer:

```json
{
  "schema": "agent_bridge.experience.v0",
  "experience_id": "exp_20260630_workflow_feedback_001",
  "scope": "project:/Data/CascadeProjects/agent-bridge",
  "goal": "Land external workflow-feedback research into AB memory/docs/forum",
  "plan": [
    "inspect local AB state",
    "write durable design note",
    "save memory",
    "post board update"
  ],
  "trajectory": {
    "tool_spans": [
      {
        "tool": "git status",
        "purpose": "verify clean branch before writing",
        "outcome": "success"
      }
    ],
    "decision_points": [
      {
        "question": "Should AB jump to RL or build read-only scorecards first?",
        "decision": "Build scorecards and experience objects first."
      }
    ]
  },
  "outcome": {
    "status": "success",
    "evidence": [
      "design document committed or reviewable",
      "memory key saved",
      "forum post created"
    ]
  },
  "reflection": {
    "lesson": "AB should close trajectory/outcome/reflection/retrieval loops before automatic policy mutation.",
    "falsifier": "If repeated reports do not produce adopted improvements or measurable behavior lift, redesign the loop."
  },
  "promotion": {
    "skill_candidate": false,
    "runbook_candidate": true,
    "runtime_influence_allowed": false
  }
}
```

The object should initially be produced by a report or script, not by a new
mandatory runtime surface.

## Maturity Scorecard

Use a small scorecard before any automatic optimizer:

| Axis | Question | Current read |
| --- | --- | --- |
| Capture coverage | Are work-loop traces, decisions, errors, and outcomes recorded? | Partial. Tool telemetry and memory/forum state exist, but not one normalized trajectory object. |
| Attribution quality | Can AB connect outcome to memory/tool/decision causes? | Partial. Edges and tool logs exist, but causal grouping is weak. |
| Feedback density | Are useful/stale/harmful/missing labels common enough? | Low. Retrieval/correction feedback exists but is sparse. |
| Retrieval influence | Does feedback affect what later sessions see? | Conservative. Some graph-aware modes may observe feedback; default FTS remains mostly unchanged. |
| Behavior lift | Can AB prove better tool choice or faster recovery? | Early. There are shadow-eval patterns, but no standing workflow lift report. |
| Governance | Are self-improvement changes reviewable and reversible? | Stronger than average. Existing AB patterns favor owner gates and docs-first design. |

## Implementation Slices

### Slice 1 - Research Landing

Status: this document.

Outputs:

- durable memory note
- board/forum post
- design document

### Slice 2 - Read-Only Workflow Feedback Report

Status: landed as v0 CLI report.

Command:

```text
agent-bridge workflow-feedback-report [--json] [--window-secs 86400] [--top-tools 10]
```

Implementation:

- `crates/bridge/src/workflow_feedback.rs`
- `crates/bridge/src/main.rs`

Compose existing data without writing policy:

- recent goals and work memory
- memory feedback counts
- MCP tool-call successes/errors
- forum decisions and open questions
- consolidation queue state
- recent commits/tests when available

Output a report with:

- top reusable lessons
- stale/harmful/missing context candidates
- tool-use friction
- likely workflow improvement actions
- falsifiers and required evidence

### Slice 3 - Experience Object Fixture

Status: landed as two manually reviewed v0 fixtures.

Fixtures:

- `docs/design/fixtures/workflow-feedback-experience-agent-send-input-2026-06-30.json`
- `docs/design/fixtures/workflow-feedback-experience-report-cli-2026-06-30.json`

Create a fixture schema and one or two manually assembled examples. The first
examples should be from completed AB lanes, not synthetic tasks.

### Slice 4 - Shadow Scoring

Status: landed as read-only CLI scorer.

Command:

```text
agent-bridge workflow-feedback-shadow-score \
  --fixture docs/design/fixtures/workflow-feedback-experience-agent-send-input-2026-06-30.json \
  --fixture docs/design/fixtures/workflow-feedback-experience-report-cli-2026-06-30.json \
  --scenario "<held-out workflow scenario>" \
  --json
```

Scenario fixture:

- `docs/design/fixtures/workflow-feedback-shadow-score-scenarios-2026-06-30.json`

Score whether a proposed lesson would have helped a held-out session. Do not
alter bootstrap, retrieval ranking, or tool routing. Produce only advisory
rankings and evidence.

### Slice 5 - Promotion Gate

Status: landed as read-only CLI gate packet.

Command:

```text
agent-bridge workflow-feedback-promotion-gate \
  --shadow-score /tmp/workflow-feedback-shadow-score-run-1.json \
  --shadow-score /tmp/workflow-feedback-shadow-score-run-2.json \
  --behavior-lift-ref "<metric or falsifiable behavior-lift anchor>" \
  --rollback-ref "<rollback path or revert handle>" \
  [--owner-approval-ref "<explicit owner approval ref>"] \
  --json
```

Evidence fixture:

- `docs/design/fixtures/workflow-feedback-promotion-gate-evidence-2026-06-30.json`

Only repeated, measured wins should promote an experience into:

- a durable memory with higher actionability
- a runbook
- a skill candidate
- a bounded retrieval influence rule

Runtime influence requires owner approval and rollback evidence.

The gate consumes previously emitted `workflow-feedback-shadow-score --json`
reports and checks:

- all shadow reports are read-only and boundary-safe
- repeated independent shadow-score reports exist
- held-out scenarios have strong top-ranked matches
- behavior-lift and rollback refs are present
- owner approval is explicit, never inferred from local evidence

### Slice 6 - Lift Evidence Metric Anchor

Status: landed as read-only CLI metric anchor.

Command:

```text
agent-bridge workflow-feedback-lift-evidence \
  --scenario-fixture docs/design/fixtures/workflow-feedback-shadow-score-scenarios-2026-06-30.json \
  --shadow-score /tmp/workflow-feedback-shadow-score-run-1.json \
  --shadow-score /tmp/workflow-feedback-shadow-score-run-2.json \
  [--baseline-correct <count> --baseline-total <count>] \
  --json
```

Evidence fixture:

- `docs/design/fixtures/workflow-feedback-lift-evidence-anchor-2026-06-30.json`

This packet turns held-out shadow-score observations into a behavior-lift ref
candidate for Slice 5. It checks read-only shadow boundaries, scenario
observation completeness, expected top-1 match accuracy, and optional measured
lift over a baseline correct/total. Without baseline it emits only a falsifiable
metric anchor (`metric_anchor_without_baseline`), not measured lift or owner
approval.

## Non-Goals

- No automatic RL training path in the near term.
- No silent prompt/profile/runtime mutation.
- No broad new MCP bundle before report-first usage proves the need.
- No feedback signal should outrank current user intent or explicit project
  constraints.

## Immediate Next Step

Use the lift-evidence packet to produce measured behavior-lift refs only after a
baseline is supplied, then feed that ref into the promotion-gate packet together
with rollback handles and owner approval refs. Any actual memory/runbook/skill/
retrieval promotion must happen in a separate authorized lane; runtime,
retrieval, and tool-routing influence remain blocked by default.
