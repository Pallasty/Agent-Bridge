# Goal C Report-First Utility Surface

Date: 2026-06-21

Plan: `ab_controlled_rsi_goal_c_20260621`, step G2.

This document defines the first report-first utility surface for controlled
recursive self-improvement in Agent-Bridge. It is intentionally a document and
runbook first. It does not add an MCP tool, does not mutate runtime state, and
does not implement an executor.

The surface is called `U` in thread #120: a small standing utility function for
whether a proposed self-improvement actually improves continuity.

## Purpose

`U` exists to answer one question before Agent-Bridge changes itself:

> Did this proposal improve externally anchored continuity, or did it only add
> another internal gate?

The report-first loop composes existing surfaces:

- continuity honest ledger inventory
- recall/cold-start metrics
- LSWR-H1 held-out direction probe, when run
- L6 falsification status
- BioCortex offline holdout status
- tool atlas and dispatch telemetry
- readiness and lifecycle status
- event-spine replayability
- work-memory handoff context
- board decisions and open questions

## Inputs

Required for every `U` report:

| Input | Source | Required Evidence |
|---|---|---|
| Ledger | `docs/design/CONTINUITY_HONEST_LEDGER_INVENTORY_2026_06_21.md` or successor | Each lane has a classification and missing-anchor note. |
| Recall metric | `recall_eval` or successor | R@1, R@5, R@10, MRR by mode; host/model selection must be explicit. |
| LSWR probe | LSWR-H1 report, once available | Baseline vs ledger-assisted cold-start direction accuracy. |
| L6 state | `docs/L6-OPTION-E-RESULT-2026-05-16.md` | Falsified/shelved state remains visible. |
| BioCortex retrieval | holdout/review docs | Offline/runtime boundary is not conflated. |
| Tool surface | `tool_atlas_snapshot` + `mcp_dispatch_audit` | Hot/cold/failing counts and action candidates. |
| Lifecycle | `readiness_audit` + `mcp_lifecycle_digest` | Setup/hook/profile health and warnings. |
| Replayability | `event_spine_snapshot` | Chain verified, chain head recorded. |
| Coordination | forum digest/read | Recent owner decisions, claims, and blockers. |
| Scratchpad | `work_memory list/get` when relevant | Active handoff state, not durable truth. |

## Current Report Prototype

This prototype was generated from live readings on 2026-06-21.

### Board Verdict

Thread #120 accepted the controlled recursive self-improvement framing:

- no runtime self-patching
- report-first loop
- no new MCP tool by default
- Goal C before executor work

Post #3736 refined the target: `U` should become a standing utility surface that
combines recall evaluation, LSWR-H1, L6 falsification, and tool-atlas pressure.

### Continuity Ledger

Current ledger file:

`docs/design/CONTINUITY_HONEST_LEDGER_INVENTORY_2026_06_21.md`

Key classifications:

- L6 C1: `falsified_shelved`
- BioCortex retrieval: offline `verified_external_anchor`, runtime
  `unfalsified_shadow_only`
- Memory-continuity T0-T7: `verified_internal_chain` plus partial held-out
  design, missing standing dashboard
- LSWR G37-G40: `verified_internal_chain` and
  `blocked_by_missing_external_anchor`
- Tool surface: `surface_contraction_candidate`

### Recall / Cold-Start Metric

Thread #120 post #3736 reported a live Mac `recall_eval` run:

| mode | R@1 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|
| fts | 0.278 | 0.500 | 0.667 | 0.379 |
| hybrid | 0.111 | 0.500 | 0.500 | 0.206 |
| semantic(e5) | 0.000 | 0.056 | 0.111 | 0.037 |

Important finding:

- semantic recall on the Mac e5 store underperformed FTS sharply;
- case #9, asking for the core Agent-Bridge vision, missed across all modes;
- `recall_eval` had a host/model anchor mismatch risk: a hard-coded `para-ml`
  anchor is wrong for Mac's current `multilingual-e5-small` store and can cause
  semantic to be skipped rather than measured.

This is currently the strongest external continuity signal. It should be
treated as the first `U` dashboard row.

### LSWR-H1

Post #3731 landed a docs-only LSWR-H1 design on
`codex/lswr-h1-heldout-probe-design`, commit `5b56a3e`.

Current state:

- design exists;
- H1 is not yet a run result;
- it does not authorize LSWR G41 or world-verdict rewrite expansion.

### Tool Surface

Current Codex Desktop MCP surface:

- `toolset=codex-lean`
- `tool_profile=essential`
- 40 exposed tools

Seven-day `tool_atlas_snapshot(source=codex, profile=essential)`:

- 40 current tools
- 16 hot
- 16 cold
- 6 failing

Seven-day `mcp_dispatch_audit(source=codex, profile=essential)`:

- 1746 total Codex-attributed calls
- 6 total errors
- hot tools include `forum_read`, `forum_post`, `capabilities`,
  `changes_digest`, `forum_digest`, `plan_update`, `mcp_lifecycle_digest`,
  `memory_search`, and `tool_atlas_snapshot`
- optimization candidates include slow `capabilities` and historical
  `memory_save` metadata validation errors

This supports surface contraction work, but the first action should be a report
candidate, not a profile edit.

### Readiness / Lifecycle

`readiness_audit(repo_root=/Users/pallasting/Projects/agent-bridge,
include_local_install=true)` reports:

- status `ready`
- setup state ready
- source coverage present
- hook sources present
- no readiness warnings

`mcp_lifecycle_digest` reports:

- lifecycle state `attention`
- MCP stdio available
- runtime health not checked in this pass
- lifecycle telemetry scoped to Codex essential/codex-lean

### Event Spine

`event_spine_snapshot(window=1d, limit=200)` reports:

- chain verified
- 200 events
- chain head
  `0090aabebd802ef9f91ba506c4a16b4728731c405d0c81e0bb281b2443918479`

This is enough for report replayability, not enough by itself for continuity
improvement.

### Work Memory

`work_memory list` shows recent active scratchpads around BioCortex graph
proximity and older memory graph hygiene/orphan tooling. These are useful
handoff breadcrumbs, but they are not durable Goal C evidence unless promoted
through a report or memory decision.

## Proposed Actions

### Action A: Preserve recall_eval host-model selection

Status: claimed by the Mac/design-lead lane in #3736.

Why it matters:

- if semantic evaluation silently skips because the wrong host/model anchor is
  used, the main continuity metric lies by omission;
- this is the first blocker to a trustworthy `U` surface.

This lane should not take the implementation unless that owner releases it.

### Action B: Build a standing `U` report artifact from existing surfaces

Status: suitable for the current Codex-RSI lane.

Expected output:

- one report file per run or one updated daily report section;
- no new MCP tool;
- links to source forum posts, docs, and telemetry snapshots;
- a compact action table with external anchor, falsifier, owner, rollback path,
  and next decision.

### Action C: Prepare G3 dry-run patch plan after Action A lands

Status: next after G2.

Candidate:

- use the fixed `recall_eval` host-model selection and the LSWR-H1 design as
  inputs;
- produce a dry-run patch plan for a minimal `U` report generator or runbook;
- compare before/after on cold-start continuity and tool-surface pressure.

## Falsifiers

This report-first lane fails if:

- `U` reports do not produce adopted actions after repeated runs;
- reports keep expanding tool surface instead of shrinking cold/failing surface;
- semantic recall remains worse than FTS and the lane cannot explain why;
- agents still authorize LSWR gate expansion when the ledger says an external
  anchor is missing;
- the report becomes another acceptance ritual that no downstream lane uses.

## Runbook

1. Read thread #120 since the last `U` report.
2. Refresh the ledger classifications.
3. Refresh recall/cold-start metrics with explicit host/model selection.
4. Include LSWR-H1 only if a run result exists; otherwise list it as design-only.
5. Run `tool_atlas_snapshot` and `mcp_dispatch_audit` for the active client,
   model, profile, and toolset.
6. Run `readiness_audit`, `mcp_lifecycle_digest`, and `event_spine_snapshot`.
7. Read relevant `work_memory` rows only as scratchpad context.
8. Emit action candidates with owner, anchor, falsifier, and rollback path.
9. Post the report summary to #120.
10. Do not add tools or mutate runtime state unless a later G3/G4 gate approves
    it.

## G2 Exit Criteria

G2 is complete when this document is committed and posted to #120 because it
provides:

- a concrete report format;
- a current sample report;
- one externally anchored action candidate;
- explicit falsifiers;
- a no-new-MCP-tool boundary;
- a next-step bridge to G3.
