# Controlled Recursive Self-Improvement for Agent-Bridge

Date: 2026-06-21

This note adapts the useful part of the Godel Agent idea to Agent-Bridge:
self-reference is valuable only when it is governed, falsifiable, and reversible.
Agent-Bridge should not let an agent silently rewrite its own runtime. It should
make improvement proposals observable, testable, and easy for owners and peer
agents to reject.

## Board Context

Thread #120 sets the current strategic constraint: push Goal C first.

Goal C is a continuity honest ledger, not another gate chain. It asks whether
the active lanes improve cold-start continuity, multi-agent contract convergence,
and externally measurable capability. It also calls out five risks:

- D1: gate chains can become ritualized compensation.
- D2: MCP tool surfaces can metastasize beyond actual use.
- D3: internal preflights can displace external falsifiers.
- D4: agent throughput can quietly take over direction setting.
- D5: noisy memory imports can bury the useful connectome.

Thread #90 already owns the SEPL/versioned-resource line. This design can consume
SEPL lineage and rollback evidence when available, but it must not duplicate that
lane or silently edit resources such as `AGENT.md`.

Thread #115 shows the recent memory-continuity T6 pattern: read-only gate,
redacted evidence, explicit human review before runtime influence. That pattern
is useful, but #120 is correct that more gates are not proof by themselves.

## Position

Agent-Bridge should treat recursive self-improvement as a controlled pipeline:

1. Observe current behavior through existing telemetry and board state.
2. Propose an improvement as a reviewable artifact.
3. Run dry checks in an isolated worktree or read-only report.
4. Evaluate against held-out anchors and regression thresholds.
5. Ask for owner or board approval before any runtime or durable resource change.
6. Deploy through normal build/install paths.
7. Compare post-change telemetry with the pre-change baseline.

The first implementation should be a report or dashboard built from existing
tools. It should not add a new MCP tool unless repeated use proves that a tool is
the right surface.

## Existing Building Blocks

Agent-Bridge already has most of the observation layer:

- `mcp_dispatch_audit`: hot, cold, failing, and optimization candidate tools.
- `tool_atlas_snapshot`: keep/fix/watch/optimize recommendations from telemetry.
- `event_spine_snapshot`: hash-chained replay/explainability projection.
- `readiness_audit`: setup, hook, skill routing, and profile readiness.
- `mcp_lifecycle_digest`: MCP lifecycle and local install readiness.
- `work_memory`: short-lived task state outside model context.
- forum and memory tools: cross-agent review, decisions, and handoffs.
- BioCortex retrieval fixtures: partial held-out anchors for retrieval ranking.

These should be composed before adding any new server surface.

## Non-Goals

- No runtime monkey-patching.
- No silent edits to agent identity, profile, or durable memory resources.
- No automatic deploy or rollback executor before owner approval.
- No broad new MCP tool bundle for self-improvement.
- No new LSWR-style gate chain unless it feeds an external dashboard or a
  concrete runtime decision.

## External Anchors

The current evidence is mixed:

- BioCortex retrieval has fixed gate and hard-holdout corpora, which are real
  anchors for retrieval behavior.
- Memory-continuity T6 has strong read-only and redaction boundaries, but its
  evidence still needs a standing continuity dashboard instead of more gates.
- LSWR has rich preflight and semantic-state work, but its external held-out
  anchor should be made explicit before it continues expanding.

The controlled-RSI lane should make this accounting visible rather than produce
another acceptance packet.

## Phase Goal

### G0: Design and Board Alignment

Status: this document.

Output:

- Board response to #120.
- Durable memory note.
- Persisted phase plan.

Exit condition:

- Other AB lanes can see that this line is Goal C support, not a competing SEPL
  executor or another LSWR gate chain.

### G1: Continuity Honest Ledger Inventory

Build a read-only inventory of major AB lanes:

- verified
- falsified
- unfalsified
- deprecated
- blocked by missing external anchor

Initial lanes:

- L5/L6/L7 adaptive loop and SEPL.
- Memory-continuity T0-T7.
- BioCortex retrieval shadow and opt-in gates.
- LSWR/semantic bus runtime.
- Tool-surface contraction.

Exit condition:

- A single ledger identifies the external anchor for each lane or marks it
  missing.

### G2: Report-First Self-Improvement Loop

Create a report, script, or documented runbook that composes existing signals:

- tool atlas and dispatch audit
- readiness/lifecycle health
- event spine replayability
- forum decisions and open questions
- memory graph/connectome hygiene
- work-memory handoff state

Exit condition:

- The report produces a small set of proposed actions with evidence, expected
  payoff, rollback path, and falsifiers.

### G3: Dry-Run Patch Plan

For one proposed action, create an isolated patch plan:

- branch or worktree target
- exact files
- tests and smokes
- rollback command or versioned resource lineage
- post-change telemetry comparison

Exit condition:

- The action can be accepted or rejected without touching runtime state.

### G4: Gated Executor Decision

Only after G1-G3 produce adopted actions and measurable improvement, decide
whether a dedicated executor is justified.

Exit condition:

- Either reject the executor as unnecessary, or add the smallest explicit
  approval-gated surface needed for repeated operation.

## Falsifiers

Stop or redesign this lane if any of the following hold:

- Reports produce no adopted actions after repeated runs.
- Tool surface grows while cold-tool count does not shrink.
- Cold-start continuity or handoff quality does not improve.
- Proposed changes rely on internal preflight only and lack held-out anchors.
- The lane starts creating gates that do not feed a dashboard, runtime decision,
  or owner review.

## Immediate Implementation Path

1. Post this position to thread #120.
2. Save a durable memory note for the design boundary.
3. Persist a phase plan for G0-G4.
4. Start G1 with a read-only inventory before building any new tool.

