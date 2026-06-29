# Cascade Portfolio: Idea Archive Read-Only Triage

Date: 2026-06-29
Status: portfolio planning memo, no runtime integration

## Decision

Treat AIMemoryPalace_v2, QMSs, QNNs, TCT/TCF/TTE, Genesis, Symbiosis,
and `symbiosis_architecture` as idea archives. They are useful for concepts,
design language, and future research prompts, but they are not current execution
spines for Agent-Bridge, BioCortex, ArrowQuant, or Onsen-HD.

No archive project was modified during this triage. This memo is stored in
Agent-Bridge as a portfolio index so future sessions can recall the boundary
without touching dirty or non-git archive trees.

## Evidence Checked

Read-only scan covered:

- repository or directory status for each archive;
- top-level directory shape;
- README and representative design documents;
- latest tracked commit summaries where a git repository exists.

Representative artifacts read:

- `AIMemoryPalace_v2/README.md`
- `AIMemoryPalace_v2/docs/README.md`
- `AIMemoryPalace_v2/docs/hybrid_architecture_plan.md`
- `QMSs/README.md`
- `QMSs/docs/integration_status.md`
- `QMSs/docs/memory_design_principles.md`
- `QNNs/README.md`
- `QNNs/docs/QUANTUM_NEURAL_NETWORK_DESIGN.md`
- `QNNs/docs/integration_status.md`
- `TCT/README.md`
- `TCT/docs/README.md`
- `TCT/v2/README.md`
- `TCF/README.md`
- `TCF/README.rust.md`
- `TCF/docs/projection_system_design.md`
- `TTE/README.md`
- `TTE/prototype/README.md`
- `Genesis/README.md`
- `Genesis/pyproject.toml`
- `Symbiosis/README.md`
- `Symbiosis/docs/UNIFIED_PROJECT_ROADMAP.md`
- `symbiosis_architecture/README.md`
- `symbiosis_architecture/part1_overview.md`
- `symbiosis_architecture/diagrams/five_layer_architecture.md`

## Archive State Summary

| Archive | Observed State | Portfolio Use |
|---|---|---|
| `AIMemoryPalace_v2` | Git repo, local `main` ahead of `origin/main` by 2; very dirty tracked state including hundreds of additions/modifications and many deletions/renames. Contains conversation archives, generated memories, configs, and likely sensitive local artifacts. | High-value concept archive for AI memory-palace language, hybrid Rust/Python memory runtime, and long-form design history. Do not ingest raw content automatically. |
| `QMSs` | Git repo on `feature/resonance-network-refactor`; very dirty tracked state with large deletion/modification counts. | Useful reference for MCP-facing memory service ideas, resonance terminology, quantum-state status tools, crawler/classifier side quests. Archive only. |
| `QNNs` | Git repo on `feature/resonance-network-refactor`; very dirty tracked state with additions/deletions/renames and VSCode extension material. | Useful reference for seven-layer QNN architecture: perception, encoding, storage, association, resonance, evolution, application. Archive only. |
| `TCT` | No `.git` observed; Python/Rust mixed research prototype with many outputs and generated plots. | Useful mathematical sandbox reference: operators, holographic fusion, fractional features, persistent homology, and v2 thought-engine vocabulary. |
| `TCF` / `TCF_v0` | No `.git` observed; Python/Rust prototype directories with outputs, checkpoints, and docs. | Useful smaller reference for transcendental-state graph/evolution and projection-system design. |
| `TTE` | No `.git` observed; Python/Rust project with tests, target output, and many direct test scripts/plots. | Useful reference for property-test style checks around fusion, evolution stability, operator consistency, and backend selection. |
| `Genesis` | Git repo at `origin/main`, but local tracked state is heavily modified. It is an external universal physics / robotics simulation engine. | Use as external embodied-physics reference only. Do not fork into Cascade mainline from this dirty checkout. |
| `Symbiosis` | Git repo aligned with `origin/master` but dirty tracked state. | Useful compact implementation/reference for thinking-model management, context matching, model evolution, and value metrics. |
| `symbiosis_architecture` | No `.git` observed; documentation-only architecture tree. | Useful clean conceptual map tying QMSs, QNN, Symbiosis, holographic storage, and AIMemoryPalace_v2 into a five-layer architecture. |

## Borrowable Ideas

### Memory And Association Language

The archive repeats a useful pattern: memory is not only storage, but a graph of
context, affect, resonance, value, and retrieval affordances. For Agent-Bridge,
the useful translation is not "quantum consciousness"; it is a practical memory
review vocabulary:

- context-bearing records;
- relationship strength;
- value/priority scoring;
- conflict and consistency checks;
- retrieval surfaces separated from write authority;
- human-reviewable evolution history.

Candidate future use: AB memory review artifacts, read-only memory graph
explainers, and negative tests for over-authorized memory ingestion.

### Layered Cognitive Architecture

QMSs/QNNs/Symbiosis converge on a layered map:

```text
perception -> encoding -> storage -> association -> resonance -> evolution -> application
```

This is useful as a design checklist for bounded agent subsystems. The current
Cascade translation should stay conservative:

- perception = evidence capture;
- encoding = schema-normalized packet;
- storage = explicit persistence;
- association = graph or index proposal;
- resonance = scoring or relevance, not mysticism;
- evolution = owner-reviewed policy or schema migration;
- application = display/report/action surface.

Candidate future use: diagrams and review checklists for AB memory and
BioCortex shadow reports.

### Projection Systems

TCF's projection-system design is a strong conceptual cousin of recent
read-only display packets. It separates high-dimensional/internal state from
user-visible semantic, visual, structural, emotional, or interactive
projections.

Candidate future use: report/display-model builders where one evidence packet
can become a forum post, dashboard card, handoff packet, or operator view
without changing the underlying evidence.

### Mathematical Sandbox Ideas

TCT/TCF/TTE contain many operator and property-test ideas: fusion, evolution
stability, entropy/energy conservation, persistent homology, interference,
fractal features, and backend selection.

Candidate future use:

- property-test inspiration for BioCortex and ArrowQuant;
- benchmark/canary language for "do not reward-hack the metric";
- read-only experiment designs before any implementation.

### Embodied Simulation Reference

Genesis is valuable as a modern physics/robotics simulation reference. It is
not a Cascade integration candidate today; its useful role is to remind us what
a mature embodied simulation platform looks like: explicit solvers, materials,
rendering, cross-platform backends, and documented scope.

Candidate future use: long-horizon embodied simulation research notes after
Onsen/Nexus/AB boundaries are settled.

## Forbidden Uses

Do not:

- auto-ingest archive files into Agent-Bridge memory;
- import raw conversations, configs, API lists, keys, caches, generated memory
  JSON, generated plots, or local runtime artifacts;
- use "quantum", "consciousness", "life", or "resonance" wording as evidence
  of capability without executable tests and falsifiers;
- treat any archive as a live runtime dependency;
- wire archive code into AB/BioCortex/Onsen execution paths;
- normalize, reset, clean, or commit dirty archive worktrees as part of this
  portfolio plan;
- use Genesis as an embodied runtime until there is an isolated clean checkout
  and explicit owner authorization.

## Re-Activation Gates

An archive can move from "idea source" to active work only when:

1. A clean or intentionally isolated worktree exists.
2. Sensitive/local artifacts are excluded or audited.
3. A single narrow objective is chosen.
4. Claims are rewritten as falsifiable checks.
5. A validation command or review artifact is defined before implementation.
6. No live AB memory/retrieval/runtime authority is granted by default.

## Suggested Future Narrow Lanes

1. **Memory vocabulary audit**: extract only terminology and schema ideas from
   AIMemoryPalace_v2/QMSs/QNNs docs into a sanitized AB memory-review glossary.
2. **Projection builder pattern**: compare TCF projection concepts with existing
   AB report/display packet builders and identify common helpers.
3. **Property-test sampler**: mine TCT/TCF/TTE tests for conservation,
   stability, and fusion-test motifs; translate into abstract test patterns,
   not code imports.
4. **Symbiosis model card**: summarize `ThinkingModel`, `ModelManager`, context
   matching, relationship network, and value metrics as a possible AB
   tool/model-card review shape.
5. **Genesis clean-room note**: separately evaluate Genesis from a clean
   upstream clone if embodied simulation becomes an active research lane.

## Portfolio Placement

Current placement:

```text
AB / BioCortex: current integration spine, read-only/reporting first.
ArrowQuant: compact ML tooling and release surface.
Onsen-HD: product/demo lab and event-sourced slice.
Nexus: long-horizon world/simulation reference, read-only.
Idea archives: concept mine only; no runtime or memory ingestion.
```

This completes the `cascade_project_portfolio_landing_2026_06_29` plan.
