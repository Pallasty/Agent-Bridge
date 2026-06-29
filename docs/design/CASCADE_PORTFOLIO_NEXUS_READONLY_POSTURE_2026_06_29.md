# Cascade Portfolio: Nexus Read-Only Posture

Date: 2026-06-29
Status: portfolio planning memo, no runtime integration

## Decision

Keep `nexus-civilization` as a long-horizon world/simulation reference for the
CascadeProjects portfolio. Do not make it the current execution spine for
Agent-Bridge, BioCortex, ArrowQuant, or Onsen-HD.

This memo is intentionally stored in Agent-Bridge rather than the Nexus
worktree. The Nexus checkout currently has local dirty generated-client
deletions and session-log edits; this portfolio decision must not modify or
normalize that worktree.

## Evidence Checked

Repository state:

- Local `nexus-civilization` branch: `main`.
- Local head observed: `6a5e901` (`Merge branch 'main' of
  github.com:pallasting/nexus-civilization`).
- Local `main` is ahead of local `origin/main` by three commits.
- `github/main` observed at `f775b20` with the AgentIdentity Phase A work.
- Dirty tree includes many tracked deletions under `client/godot/.godot/` and
  `client/godot/android/build.bak.*`, plus
  `production/session-logs/session-log.md`.

Reference artifacts read:

- `docs/API_CONTRACT.md`
- `docs/CLIENT_PROTOCOL.md`
- `docs/META_LAYER.md`
- `docs/RUST_MIGRATION.md`
- `docs/ROADMAP.md`
- `docs/NexusCivilization_Design_Document.md`
- `production/project-stage-report.md`
- `production/research/README.md`
- `AGENT_PROTOCOL.md`

## Valuable Patterns To Borrow Later

### Multi-Client World Projection

Nexus has a clear pattern for one authoritative world state projected into
multiple client views: `slg`, `rpg`, `trade`, and `explore`. The key useful
idea for Cascade is not the specific game mechanics; it is the adapter contract:
one world snapshot, multiple view-specific projections, and client-specific
actions translated into a shared command pipeline.

Candidate future reuse:

- AB dashboards that project the same memory/project state into different
  operator views.
- Onsen data surfaces that preserve one event-sourced truth while supporting
  product, QA, and art-direction views.
- BioCortex review surfaces that keep a stable evidence packet but allow
  different read-only presentations.

### Unified Command Pipeline

The documented seven-stage command pipeline is useful as a design reference for
gated actions: format, authority, permission, resources, constitution/rules,
rate, and impact. This maps well to Agent-Bridge's gated-action direction, but
only as a reference. Do not import Nexus commands or make Nexus a live policy
authority.

Candidate future reuse:

- Read-only comparison against AB `gated_action` and authorization packets.
- A design checklist for command/action review artifacts.
- Negative-test inspiration for rejecting malformed or over-authorized actions.

### Event And Causal Graph Discipline

Nexus treats world updates as events with causal traces and has tests covering
causal governance linkage. This is valuable for AB memory and Onsen event
analysis because it encourages explaining why a state changed rather than only
showing the latest state.

Candidate future reuse:

- Causal readback format for project board updates.
- Event lineage for Onsen service-loop evidence.
- Read-only AB memory review artifacts that show why a proposed edge exists.

### Research-Loop Harness

`production/research/README.md` captures a healthy research loop shape:
freeze baseline, define metric, add canaries, run parallel experiments, then
review top candidates. That is directly relevant to AB/BioCortex evaluation
lanes.

Candidate future reuse:

- Shadow-only experiment plans for memory retrieval changes.
- BioCortex recall/ranking comparisons with explicit canaries.
- ArrowQuant benchmark gates where quick wins can otherwise reward-hack.

### Rust And Arrow Migration Notes

`docs/RUST_MIGRATION.md` and the Arrow schema notes are useful as a reference
for moving hot paths across language boundaries. The portfolio has already
favored Arrow-like evidence surfaces in Onsen and ArrowQuant, so Nexus remains
useful as a prior art archive for boundary contracts.

Candidate future reuse:

- Read-only schema-contract reviews.
- Rust/Python boundary audit checklists.
- Event batch and snapshot interchange design.

## Current Non-Integration Reasons

Nexus is not the current execution spine because:

- The checkout is not clean enough for safe portfolio edits.
- The product scope is much broader than the current AB/BioCortex/Onsen lanes.
- It mixes world simulation, game client, SDK, research, governance, and Godot
  artifacts; importing it wholesale would increase coordination load.
- Current portfolio progress is better served by narrow validated slices:
  BioCortex read-only reports, ArrowQuant release hardening, and Onsen service
  loop evidence.
- Any live coupling would risk confusing a reference world engine with an
  authority source for AB memory, retrieval, runtime, or project planning.

## Allowed Uses

Use Nexus as:

- architecture reference;
- protocol-reference library;
- research-loop/canary pattern source;
- future long-horizon simulation benchmark candidate;
- documentation archive for multi-client world projection and causal events.

Allowed actions:

- read docs and tests;
- summarize patterns into AB design notes;
- compare ideas against AB/Onsen/BioCortex boundaries;
- open future read-only research-cycle plans.

## Forbidden Uses

Do not:

- write Agent-Bridge memory or retrieval edges from Nexus state automatically;
- make Nexus the source of AB runtime, policy, or authorization decisions;
- import Nexus world ticks into AB/BioCortex/Onsen execution paths;
- start federating Nexus/Onsen/AB runtime loops;
- clean, reset, or normalize the dirty Nexus worktree as part of this portfolio
  step;
- treat generated Godot cache deletions as an actionable task without a
  dedicated owner decision.

## Re-Activation Gates

Nexus may move from read-only reference to active work only when all of the
following are true:

1. A clean or intentionally isolated worktree exists.
2. Remote topology is clarified (`github` vs local `origin`) and the desired
   upstream is explicit.
3. A single narrow objective is selected, such as protocol documentation,
   research-loop benchmark, or causal-event review.
4. A focused validation command is identified before edits begin.
5. The work does not introduce live runtime coupling with Agent-Bridge,
   BioCortex, or Onsen without owner authorization.

## Portfolio Placement

Current placement:

```text
AB / BioCortex: current integration spine, read-only/reporting first.
ArrowQuant: compact ML tooling and release surface.
Onsen-HD: product/demo lab and event-sourced slice.
Nexus: long-horizon world/simulation reference, read-only.
Idea archives: mine later after dirty-tree and claim audits.
```

Next portfolio step after this memo: `p3-idea-archive`.
