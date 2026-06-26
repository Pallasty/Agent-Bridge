# Memory Continuity Cognitive Architecture

Date: 2026-06-19
Status: design landing; no runtime behavior change
Forum: design board #115
Memory: `ab_memory_continuity_cognitive_architecture_20260619`

## Purpose

Agent-Bridge memory exists to provide continuity for the agent, but continuity
is not free. Every remembered item can reduce uncertainty, but it can also add
context cost, anchoring, stale assumptions, and retrieval noise.

This memo lands the current design frame:

- memory storage is the base capability;
- retrieval efficiency and context-budget discipline are the real evolution
  path;
- continuity must be layered by role and time horizon;
- deterministic governance should remain the authority layer;
- BioCortex-rs and future neural memory layers should begin as shadow
  side-signals, not as write-authorized memory owners.

## Related Records

- `docs/DESIGN-v22-agent-bridge-memory-substrate.md`
- `docs/DESIGN-work-memory-scratchpad-2026-05-23.md`
- `docs/design/BIOCORTEX_INTEGRATION_ASSESSMENT_2026_06_10.md`
- `docs/design/BIOCORTEX_RETRIEVAL_DEFAULT_INFLUENCE_CONTRACT_2026_06_11.md`
- `docs/design/BIOCORTEX_RETRIEVAL_OPT_IN_EXPERIMENT_PLAN_2026_06_11.md`

## Core Thesis

The target is not "remember more." The target is:

> restore the right state, constraints, evidence, and operating posture with
> the smallest necessary context footprint.

Memory should behave like an attention scheduler. It should decide what needs
to enter context now, what should stay queryable but cold, what should be
archived, and what should be treated as stale or contradictory.

## Deterministic Governance Layer

AB's current memory architecture is strongest where it is programmatic:

- typed memory records (`decision`, `lesson`, `todo`, `session_handoff`,
  `work_memory`, etc.);
- scopes (`project:*`, global, exploratory);
- FTS / semantic / hybrid retrieval;
- graph edges and related-key topology;
- access counts, importance, decay, compaction, and orphan hygiene;
- lifecycle hooks (`precompact`, `stop`, `sessionEnd`);
- read-only diagnostics and runtime health checks.

This layer should keep authority over:

- what is persisted;
- what can mutate retrieval behavior;
- what evidence is required before adoption;
- what is allowed to enter default session context;
- what is archived, superseded, or treated as stale.

Its weakness is not lack of control. Its weakness is that control surfaces can
become too numerous, too rigid, and too expensive to tune manually.

## Continuity Layers

Continuity should be separated into lanes with different budgets and
lifetimes.

| Layer | Role | Storage candidate | Default context policy |
|---|---|---|---|
| Active task state | Current files, hypothesis, tests, next step | `work_memory` | small, early, TTL |
| Project state | current architecture, decisions, live risks | `decision`, `context`, `session_handoff` | compact digest only |
| Procedure | reusable ways to work and verify | skill or `lesson` | trigger-based |
| Evidence | commands, checks, proof, caveats | `decision`, `finding`, audit docs | cite when claim depends on it |
| Identity/preference | durable user/agent working style | profile or high-confidence memory | tiny, stable |
| Archive | historical trace, old handoffs, stale results | archived/superseded memory | query-only |

The default bootstrap should inject a continuity kernel, not a history dump.

## Continuity Kernel

The continuity kernel is the small context block that should be present at
session start. It should contain only:

1. active work memory;
2. the latest relevant handoff, compressed to current state and next gate;
3. high-severity project hazards;
4. currently binding verification or safety constraints;
5. explicit stale/conflict warnings when relevant.

Everything else should be index-first and loaded on demand.

## Retrieval Cost Model

A memory should pay for its context slot. A practical scoring model:

```text
context_value =
    relevance
  * confidence
  * actionability
  * freshness
  * scope_fit
  - token_cost
  - anchoring_risk
  - duplication_penalty
```

This does not need to start as a complex model. It can begin as explicit
metadata and deterministic ranking adjustments.

Recommended metadata additions:

- `continuity_role`: `state`, `constraint`, `procedure`, `evidence`,
  `preference`, `warning`, `archive`
- `retrieval_trigger`: short natural-language condition for future recall
- `confidence`: `verified`, `observed`, `inferred`, `user_stated`, `stale`
- `freshness_policy`: `never_expires`, `ttl`, `version_bound`,
  `project_phase_bound`
- `actionability`: `background`, `plan_influence`, `must_block`,
  `needs_review`
- `blast_radius`: `current_task`, `project`, `cross_project`, `global`
- `supersedes` / `superseded_by`

## Anti-Continuity Mechanisms

Continuity can become anchoring. AB should support deliberate anti-continuity
modes:

- fresh-review mode: reduce historical injection before code review or design
  critique;
- contradiction retrieval: retrieve conflicting and superseded records beside
  supporting records;
- stale gate: downrank records bound to old branches, old versions, or closed
  project phases;
- blank-slate checkpoint: ask what the answer would be without prior memory
  before adopting old conclusions;
- evidence-first mode: require proof records before a memory can influence a
  high-risk change.

These modes protect the agent from overfitting to its own history.

## Consolidation Path

Episodic handoffs are valuable but expensive. Long-term memory should be
distilled periodically:

- handoff facts -> `fact` / `context`
- durable choices -> `decision`
- reusable failures -> `lesson`
- open work -> `todo` or `work_memory`
- old process trace -> archived record
- obsolete claims -> superseded record with pointer to replacement

The target is not to delete history. The target is to keep old history
queryable while preventing it from becoming default context.

## BioCortex-rs Role

BioCortex-rs should not replace AB memory governance. It can complement it as
a deterministic neural-dynamics sidecar.

Current useful roles:

1. Shadow retrieval engine
   - S69/S72 show graph-proximity ranking and read-only retrieval-engine
     synthesis.
2. Competitive selection
   - S70-style inhibition can reduce near-duplicate candidate floods.
3. Learned association graph
   - S71-style co-occurrence learning maps naturally to AB coactivation data.
4. Stability/plasticity research
   - S90/S91 show why one competition primitive fails to rescue interference
     and how selective consolidation gating can protect old associations while
     preserving new learning.

Boundary:

- BioCortex may emit side-signal ranking, suppression, and consolidation
  suggestions.
- AB remains the authority for persistence, default retrieval behavior, and
  write gates.
- Default search order must remain baseline unless an explicit opt-in gate and
  evidence packet authorize a named call site.

## Neural Memory Extension Path

Future neural memory should advance through gated stages.

### Stage 1: Shadow re-ranker

Input: baseline AB candidates, query, metadata, graph neighborhood.
Output: side-signal scores and an alternate order.
Authority: none.

### Stage 2: Retrieval critic

Output labels:

- `used`
- `ignored`
- `stale`
- `duplicate`
- `harmful`
- `missing`
- `too_large`

Authority: telemetry only.

### Stage 3: Learned consolidation advisor

Suggests merge, archive, supersede, promote-to-kernel, or add-edge actions.
Authority: proposal only; AB deterministic gates perform writes.

### Stage 4: Temporal graph memory

Learns which subgraphs help which task types, with validity windows and
conflict awareness.
Authority: opt-in ranking influence only.

### Stage 5: Controlled memory evolution

Allows bounded automatic memory structure updates after review packets,
rollback handles, and measurable recall lift.
Authority: narrow, auditable, revocable.

## Implementation Tracks

### T0: Baseline measurement

Measure current recall and context cost before changing behavior:

- memory query hit/miss rate;
- p50/p95/p99 latency by mode;
- bootstrap token budget by section;
- duplicate retrieved records;
- stale or superseded records injected;
- retrieval feedback coverage.

### T1: Metadata schema

Add optional fields or tags for continuity role, confidence, freshness policy,
retrieval trigger, actionability, and blast radius.

No ranking change until a migration/read path proves backward compatibility.

### T2: Bootstrap budgeter

Make `session_bootstrap` emit a sectioned budget report:

- continuity kernel;
- active work;
- project state;
- hazards;
- optional recall candidates.

Each item should include why it was retrieved.

### T3: Retrieval feedback

Record post-use feedback for retrieved memories. Start with explicit tool or
lightweight telemetry; do not infer strong labels silently.

### T4: Consolidation queue

Create a read-only consolidation candidate report:

- handoff-to-decision candidates;
- duplicate lessons;
- stale warnings;
- high-token low-use records;
- orphan records that should remain orphaned.

### T5: BioCortex shadow trial

Feed baseline candidates and coactivation graph slices to BioCortex-rs. Compare
the alternate order and suppression set against AB baseline without changing
default results.

### T6: Opt-in influence experiment

Only after T5 shows lift, enable per-call or per-session opt-in influence under
the existing BioCortex default-influence contract.

### T7: Neural critic prototype

Prototype a neural retrieval critic using saved retrieval episodes. Keep it
offline until it beats deterministic baselines on held-out cases.

## Acceptance Gates

No implementation track should claim success without:

- before/after metrics;
- a disabled-path test proving current behavior is preserved;
- fallback behavior for missing neural sidecar;
- latency guardrails;
- rollback or kill switch;
- a review packet for default-path influence;
- evidence that context cost did not increase faster than recall quality.

## Open Questions

1. Should continuity metadata live as first-class columns, JSON metadata, or
   tags first?
2. What is the minimum useful retrieval feedback vocabulary?
3. Which section of `session_bootstrap` should own the continuity kernel?
4. Should BioCortex-rs consume only candidate rows, or also graph-neighborhood
   edge slices?
5. What is the first held-out recall corpus for a shadow re-ranker trial?
6. Which contexts should default to fresh-review mode?

## Current Recommendation

Start with T0-T3. They improve observability and control without granting any
new mutation authority. Keep BioCortex-rs in T5 shadow mode until AB has a
measured recall baseline and a feedback corpus.

The governing principle:

> AB owns memory truth and safety. BioCortex-rs and future neural layers may
> propose attention, competition, and consolidation signals, but they earn
> influence only through measured lift and explicit gates.
