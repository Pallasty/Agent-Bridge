# DESIGN - Context Governor Snapshot v0

Date: 2026-06-23
Status: proposed for v0 implementation

## Problem

Codex and other eager MCP clients can carry three different kinds of context
cost:

- conversation history and tool outputs already inside the model window;
- startup or hook-injected memory context;
- eager tool schema surface.

Agent-Bridge cannot edit or delete content that a host has already placed into
the model window. It can, however, govern the context lifecycle around the host:
estimate pressure, preserve active state before compaction, bound bootstrap
injection, and keep the exposed tool surface small.

## Verified State

The current implementation already has most primitives:

- `ab-memory-hook` injects scoped memory on `UserPromptSubmit` with a cooldown.
- `ab-precompact-hook` captures the transcript tail and calls
  `session_lifecycle_step(precompact)`.
- `work_memory` persists short-lived active task state outside the model
  context.
- `session_bootstrap` renders scoped memory through per-block token budgets.
- `context_budget` and `context_pressure_estimate` provide offline pressure
  estimates.
- Before this v0, Codex Desktop was running `AGENT_BRIDGE_TOOLSET=codex-lean`,
  exposing 40 tools rather than the wider standard surface.

The missing primitive is an operator-facing, read-only decision packet that
answers: "What should the agent do now to protect context quality?"

## Non-Goals

- Do not claim to prune the live Codex model context.
- Do not auto-delete transcript turns, tool results, or user messages.
- Do not write memory, compact the session, or change tool exposure from the v0
  snapshot tool.
- Do not introduce an LLM judge for relevance in v0.

## v0 Tool

Add a read-only MCP tool:

```text
context_governor_snapshot
```

Inputs:

- `cwd`: project scope, default current directory.
- `model`: model hint for context window lookup.
- `context_window`: explicit model window override.
- `conversation_turns`: coarse pressure estimate when no transcript text is
  available.
- `text_sample`: optional recent transcript or excerpt.
- `compact`: compact output flag.

Output schema:

```text
agent_bridge.context_governor.snapshot.v0
```

Fields:

- `direct_model_context_pruning`: always false in v0, with an explanation.
- `pressure`: estimated tokens, percent used, fatigue tier, recommendation,
  confidence, and distance to the 80 percent soft trigger.
- `controls`: current toolset/profile/exposed tool count and the existing
  lifecycle surfaces available for context governance.
- `suggested_actions`: ranked actions such as save `work_memory`, use
  semantic `session_bootstrap`, run precompact/finalize, keep `codex-lean`, or
  start a clean handoff.
- `guardrails`: no mutation, no remote execution, no live context deletion.

## Recommendation Rules

- `fresh`: keep current flow; use semantic bootstrap only when task scope shifts.
- `engaged`: save active `work_memory` before starting a long new branch.
- `strained`: save `work_memory`, avoid broad file dumps, prefer targeted
  retrieval, and prepare a handoff or compaction point.
- `saturated`: stop expanding the current thread; save scratch state and move to
  handoff/compact before continuing.

If no `text_sample` is provided, mark confidence as low and recommend passing a
recent transcript excerpt before making aggressive decisions.

## Placement

Expose the tool in `codex-lean`. It adds one small read-only schema, bringing the
lean profile from 40 to 41 tools, but gives Codex a native context-governance
entrypoint. It should also be visible in standard profiles through the normal
Essential tier.

## Acceptance Criteria

- The tool is read-only and does not require a store.
- The tool returns `direct_model_context_pruning.supported=false`.
- It uses the same context-window precedence as `context_pressure_estimate`:
  explicit arg, then `AGENT_BRIDGE_CONTEXT_WINDOW`, then model default.
- `codex-lean` exposes the tool.
- Unit tests cover fresh, saturated, explicit window, no-sample confidence, and
  codex-lean exposure.
