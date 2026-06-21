# Continuity Honest Ledger Inventory

Date: 2026-06-21

Plan: `ab_controlled_rsi_goal_c_20260621`, step G1.

This is the first read-only inventory for Goal C. It classifies active
Agent-Bridge continuity lanes by what they actually prove today. The purpose is
to prevent internal gate chains from being mistaken for external continuity
improvement.

## Current Board Signal

Thread #120 is the controlling direction for this pass.

- #3724 requests Goal C first: continuity honest ledger, external falsifiability,
  tool-surface contraction, and direction-right recovery.
- #3727 records the controlled recursive self-improvement design: report-first,
  no runtime self-patching, and no new MCP tool by default.
- #3728 records the LSWR lane-inner guard: G37-G40 are useful internal-chain
  proof, but LSWR should pause further gate expansion until it has a held-out
  continuity anchor.
- #3731 records an LSWR-H1 docs-only held-out probe design on branch
  `codex/lswr-h1-heldout-probe-design`, commit `5b56a3e`. This is useful input
  for Goal C, but it is not evidence that H1 has run or that LSWR should resume
  implementation expansion.

Thread #90 remains the SEPL/versioned-resource lane. This ledger may consume
SEPL lineage later, but it must not duplicate or preempt that lane.

Thread #115 remains the memory-continuity governance lane. T6 is a useful safety
pattern, but it is not itself a continuity dashboard.

## Live Telemetry Snapshot

Observed during this pass:

- Codex Desktop is on `gpt-5.5`, `xhigh`, `toolset=codex-lean`,
  `tool_profile=essential`, with 40 exposed MCP tools.
- `tool_atlas_snapshot(source=codex, profile=essential, window=7d)` reported
  40 observed tools, 16 hot, 15 cold, and 6 failing.
- `mcp_dispatch_audit(source=codex, profile=essential, window=7d)` reported
  1720 total Codex-attributed calls and 5 errors.
- `event_spine_snapshot(window=1d, limit=200)` verified a SHA-256 chain with
  200 events and chain head
  `8a197170a17178c70bb06cd0a2a7c4481510d48a2707c9aed88a5b0ed0047558`.
- `docs/design/` currently has 190 direct files, including 115
  `LIVE_SEMANTIC_WORLD*` files.

These numbers are not long-term truth. They are a timestamped baseline for this
inventory and should be refreshed before any profile or surface change.

## Classification Vocabulary

- `verified_external_anchor`: passed a held-out or externally grounded metric.
- `verified_internal_chain`: proves contract propagation, safety, or read/write
  authority boundaries, but not external continuity improvement.
- `falsified_shelved`: tested against a gate and honestly failed or was shelved.
- `unfalsified_shadow_only`: has safe shadow evidence but no runtime authority.
- `blocked_by_missing_external_anchor`: should not expand implementation until a
  held-out external anchor is defined.
- `surface_contraction_candidate`: useful capability exists, but current surface
  area or usage pattern needs contraction.

## Ledger

| Lane | Current Classification | Evidence | Honest Claim | Missing Anchor / Next Probe |
|---|---|---|---|---|
| L6 C1 introspect recall / hallucination gate | `falsified_shelved` | `docs/L6-OPTION-E-RESULT-2026-05-16.md` reports three falsified attempts, max Youden's J `+0.000`, and rule-3 shelve. | The L6 falsifiability discipline worked. The signal remains raw observability, not an authoritative hallucination gate. | Do not reopen C1 without reframing the gap or getting owner/sibling approval for a legitimate same-design rerun. |
| L5/L7 adaptive loop and SEPL | `verified_internal_chain` for roadmap/decision governance; implementation ownership external to this pass | Thread #90 owner decision approved phased SEPL: P0 read-only lineage, P1 AGENT.md first target, P2 memory mutation after e5/graph hygiene, P3 rollback later. | Versioned-resource direction is governed and propose-only; this pass does not own it. | Ledger should later import SEPL readback-hash falsifiers when they exist. |
| BioCortex retrieval side-signal policy | `verified_external_anchor` for offline retrieval ranking; `unfalsified_shadow_only` for runtime influence | Current, easy holdout, and hard-holdout corpora exist. Candidate-strong policy passed current and hard holdout with zero regressions, but runtime mutation remains forbidden. | Offline side signal has measurable retrieval value on hard holdout. | Runtime retrieval mutation still needs a separate boundary design, latency SLO, disable switch, and owner approval. |
| Memory-continuity T0-T7 | `verified_internal_chain` plus partial held-out design | T0 relies on recall_eval held-out harness; T5-T7 are redacted/read-only/shadow-only; T6 denies runtime influence. | Governance boundaries are strong. T6 is a useful pattern for safe influence review. | Needs a standing continuity dashboard: cold-start/handoff quality, adopted-action rate, and external continuity effect, not just gate readiness. |
| LSWR G37-G40 / semantic world runtime gate chain | `verified_internal_chain`; `blocked_by_missing_external_anchor` | #3728 classifies G37-G40 as internal-chain proof. Local docs show high LSWR doc surface. G40 proves evidence-to-review propagation but not continuity lift. #3731 adds an H1 design branch, but no H1 run result yet. | LSWR contract/evidence propagation is real and useful. It should not continue to G41/world-verdict rewrite until an external anchor exists. | Consume `LSWR-H1 cold-start direction continuity probe` after it is integrated or run: held-out prompts, gold labels from forum/commit/doc evidence, and false-permission checks. |
| Tool-surface contraction | `surface_contraction_candidate` | Current Codex essential surface has 40 tools, 15 cold in 7d, and 6 failing in Tool Atlas. #120 cites broader all-registry expansion pressure. | Codex-facing lean profile is much smaller than all-registry, but there is still visible cold/failure pressure. | G2 should report candidate demotions or skill/CLI moves only after separating current-profile cold tools from registry-wide cold tools. |
| Memory graph / connectome hygiene | `blocked_by_missing_external_anchor` for Goal C dashboard health | Prior graph hygiene tools and orphan previews exist, but this pass did not run a fresh graph topology check because the current Codex toolset does not expose that surface directly. | Graph/connectome health is relevant to continuity, but should not be asserted from stale counts. | Refresh topology via the appropriate deployed surface or a non-MCP CLI/report path before G2 uses graph health as an input. |

## Immediate G2 Inputs

G2 should be a report-first loop, not a tool-first implementation. Its first
report should contain:

1. Lane ledger rows from this document.
2. Live tool atlas and dispatch audit snapshots.
3. Event-spine replayability status.
4. Forum open questions that block direction decisions.
5. Memory graph/connectome hygiene status, refreshed through a valid surface.
6. Proposed actions with explicit falsifiers and rollback path.

## Do Not Do Next

- Do not implement a Godel-style runtime self-patcher.
- Do not add a new MCP tool for this lane before the report format proves useful.
- Do not resume LSWR gate expansion until LSWR-H1 or an equivalent held-out
  continuity probe is accepted.
- Do not treat BioCortex runtime influence as approved because offline
  side-signal ranking passed hard holdout.
- Do not mutate SEPL resources from this lane; consume SEPL evidence only after
  its owner lane lands it.

## Proposed G2 Acceptance Criteria

G2 can be marked complete when a report prototype, runbook, or script produces:

- a refreshed copy of the ledger;
- at least one externally anchored next action;
- at least one explicit stop/falsifier condition;
- no new MCP registry surface;
- board-visible output that another agent can inspect without reading this chat.
