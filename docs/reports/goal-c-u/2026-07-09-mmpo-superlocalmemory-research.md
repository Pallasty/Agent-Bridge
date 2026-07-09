# MMPO and SuperLocalMemory Research Map

Date: 2026-07-09

Run type: external research synthesis / docs-only planning anchor

Local base commit: `893d5cc0`

External sources:

- MMPO paper: https://arxiv.org/abs/2605.30159
- MMPO HTML: https://arxiv.org/html/2605.30159
- SuperLocalMemory V3.3 paper: https://arxiv.org/abs/2604.04514
- SuperLocalMemory V3.3 HTML: https://arxiv.org/html/2604.04514
- SuperLocalMemory repository: https://github.com/qualixar/superlocalmemory
- SuperLocalMemory site: https://superlocalmemory.com
- npm downloads API:
  https://api.npmjs.org/downloads/point/last-month/superlocalmemory

## Fact Correction

The two requested items are distinct:

- `arXiv:2605.30159` is **Meta-Cognitive Memory Policy Optimization for
  Long-Horizon LLM Agents** (MMPO), submitted 2026-05-28.
- `arXiv:2604.04514` is **SuperLocalMemory V3.3: The Living Brain**,
  submitted 2026-04-06.

There is also version/license drift on SuperLocalMemory:

- The V3.3 paper states Elastic License 2.0 and reports V3.3 capabilities.
- The current GitHub repository and package metadata checked on 2026-07-09 show
  `v3.6.22` and `AGPL-3.0-or-later`.
- npm download API returned `5715` downloads for `2026-06-09..2026-07-08`.
- PyPI metadata also reports `3.6.22` and `AGPL-3.0-or-later`, but PyPIStats
  recent-download API returned HTTP 429 during this pass, so PyPI download
  volume is not independently verified here.

Planning implication: do not import SuperLocalMemory code or package into AB.
Borrow ideas only unless a separate license review clears the exact version and
surface.

## Verdict

Adopt both as design signals, not dependencies.

MMPO is useful because it gives AB a better question than "did the final task
succeed?": did the intermediate memory state preserve a clear belief about task
progress and missing information?

SuperLocalMemory is useful because it validates several AB directions already
underway: local-first memory, bounded lifecycle, multi-channel retrieval,
quantization, code graph links, daemon warmth, and hook-driven lifecycle. But
its current licensing, implementation scope, and benchmark comparability make
direct integration inappropriate.

Recommended next move:

```text
belief-clarity diagnostic packet -> read-only report
```

Use MMPO's anchor-question idea to score AB session summaries, workflow-feedback
reports, and Experience candidates. Keep SuperLocalMemory as a borrow-pattern
backlog, with no runtime dependency.

## MMPO Read

MMPO's core problem is intermediate credit assignment. Recursive summaries can
drop task-relevant details or add semantic noise long before a final answer
fails. Outcome-only rewards cannot identify which summary introduced the
degradation.

The useful concepts for AB:

- **Belief Entropy:** a self-supervised proxy for how uncertain the model remains
  about the latent task state given the current memory.
- **Anchor question:** a progress-plus-gap probe asking what the current task
  progress is and what information is still needed.
- **Dense memory-specific supervision:** evaluate intermediate memory states,
  not only terminal success.
- **Risk warning:** direct-answer confidence can reward premature certainty; the
  better probe targets progress and missing information.

AB should not copy MMPO's training loop. The PPO/RL layer is out of scope. The
borrow is the diagnostic shape:

```text
memory/report candidate -> progress+gap probe -> uncertainty / missing-info
diagnostic -> reviewer-visible blockers
```

## SuperLocalMemory Read

SuperLocalMemory V3.3 claims these relevant pieces:

- local SQLite-backed memory with separate stores for memories, learning
  signals, and code graph;
- seven retrieval channels: semantic, keyword, entity graph, temporal,
  spreading activation, consolidation, and Hopfield associative retrieval;
- Ebbinghaus-style forgetting coupled to progressive quantization;
- code graph from tree-sitter plus rustworkx;
- warm daemon mode with store-first pending writes;
- session hooks for auto-recall, auto-observe, auto-save, consolidation, and
  forgetting;
- soft-prompt parameterization as provider-independent implicit memory.

Current repository/site drift adds these current-state facts:

- repo currently presents V3.6.22, not V3.3;
- repo license is AGPL-3.0, with commercial-license path;
- current package metadata reports AGPL-3.0-or-later;
- repo itself says the papers are arXiv preprints with Zenodo DOIs, not
  conference-accepted or journal-published work.

AB should treat SuperLocalMemory as a pattern library and claim source, not as
a dependency candidate.

## Agent-Bridge Mapping

| External pattern | AB equivalent | Fit |
| --- | --- | --- |
| MMPO belief entropy | `workflow_feedback_*`, `session_reflect`, handoff quality reports, Experience candidate review | Strong. Add a read-only belief-clarity report before changing runtime behavior. |
| MMPO progress+gap anchor | AB task handoff and `work_memory` completeness checks | Strong. Fits current context-governor and workflow-feedback direction. |
| SLM multi-channel retrieval | FTS, semantic embeddings, graph edges, coactivation, related-key preflight, retrieval outcome telemetry | Strong conceptually. AB should measure channel contribution first, not add channels blindly. |
| SLM Ebbinghaus forgetting | `memory_decay_importance`, `memory_decay_unused_importance`, retrieval-outcome reinforce/decay, outcome-gated consolidation | Strong but already partially covered. Borrow calibration/reporting, not a new decay model. |
| SLM quantization | `ab_store::quant`, INT8 shadow proposal, quant recall/drift gates | Strong. AB already has a safer owner-gated quant path; FRQAD is a research watch item, not a replacement. |
| SLM code graph | AB codebase symbols, memory graph, semantic events, related-key materialization | Medium. Useful later, but code graph should remain explicit, read-only, and privacy-safe first. |
| SLM auto hooks | AB hooks, session bootstrap/finalize, work memory, present outcomes | Medium. AB should keep fail-open hooks, but avoid auto-write expansion without owner gates. |
| SLM soft prompts | AGENT.md profile loop, workflow-feedback promotion, skills/runbooks | Medium. AB can generate explicit prompt/runbook candidates, but no silent profile/skill mutation. |

## Borrow Candidates

### P0: Belief-Clarity Diagnostic Report

Create a docs/report or read-only tool proposal that evaluates an intermediate
memory artifact with the MMPO progress+gap anchor:

```json
{
  "schema": "agent_bridge.memory_belief_clarity_diagnostic.v0",
  "memory_evolution_stage": "reflection",
  "artifact_kind": "session_handoff|workflow_feedback|experience_candidate",
  "anchor_question": "Based on current memory, what is current task progress and what information is still needed?",
  "progress_claims": ["..."],
  "missing_information": ["..."],
  "uncertainty_markers": ["..."],
  "premature_certainty_risk": false,
  "promotion_allowed": false,
  "may_write_memory_now": false,
  "may_change_retrieval_order_now": false
}
```

First target: run it over Experience rule candidates and session handoffs as a
review aid. Do not compute token-level entropy yet; start with structured
progress/gap extraction and reviewer-visible uncertainty flags. Token-level
entropy can be a later optional LLM-backed diagnostic if it is worth the cost.

### P1: Multi-Channel Retrieval Contribution Report

SuperLocalMemory's key lesson is not "add seven channels." It is that channel
fusion can help multi-hop/adversarial retrieval but can hurt single-hop
precision if routing is blunt.

AB should produce a read-only channel-contribution report:

- FTS-only;
- semantic-only;
- graph-neighborhood;
- coactivation/related-key expansion;
- hybrid/current order;
- query class: direct fact, multi-hop, temporal, procedure, stale/conflict.

The output should show which channel found the evidence and where extra channels
added noise. This directly supports query-dependent routing before any ranking
change.

### P1: Store-First Pending Memory Pattern

SLM's daemon mode stores pending memory before asynchronous processing. AB
already has strong SQLite durability, but some producer lanes still benefit
from an explicit pending/admission split.

Borrow shape:

```text
raw event -> pending/admission row -> deterministic projection -> review/gate -> durable memory
```

This is relevant for present outcomes, workflow feedback, and future desktop or
code-graph observations. It should be docs-first unless a current producer has a
measured loss window.

### P2: FRQAD / Mixed-Precision Watch Item

AB already has an INT8 quantization shadow path and recall/drift gates. SLM's
FRQAD is interesting because it treats quantization uncertainty as part of the
distance metric. But it should not replace AB's cosine recall gate until:

- the math is reimplemented clean-room or the license is cleared;
- AB has a frozen mixed-precision evaluation corpus;
- recall/rank impact is measured against existing f32 and INT8 gates;
- no live retrieval path changes before owner approval.

Near-term action: add FRQAD to the quantization watchlist, not to code.

### P2: Soft-Prompt Parameterization as Explicit Candidates

SLM's soft-prompt parameterization maps to AB's Experience stage. AB should keep
the explicit review pattern:

- source observations;
- extracted pattern;
- confidence/evidence count;
- counterexamples;
- proposed prompt/runbook text;
- owner gate;
- rollback path.

No silent AGENT.md, skill, or prompt mutation.

## Anti-Goals

Do not:

- import `superlocalmemory` npm/PyPI packages into AB;
- vendor SuperLocalMemory source while license/version is drifting;
- use SuperLocalMemory benchmark claims as AB evidence without local replay;
- add a seven-channel retrieval stack before measuring channel contribution;
- add belief-entropy training or PPO to AB;
- let any anchor-probe score directly mutate memory, ranking, or prompts;
- use auto hooks to expand write authority beyond existing gates.

## Proposed Next Slice

Name: `belief_clarity_diagnostic_packet`

Type: docs/report first.

Scope:

1. Define the AB `memory_belief_clarity_diagnostic.v0` schema.
2. Select 3-5 existing AB artifacts:
   - a session handoff;
   - a workflow-feedback report;
   - an Experience candidate;
   - a consolidation/queue report.
3. Apply the progress+gap rubric manually or with a local read-only script.
4. Report whether each artifact preserves task progress, missing information,
   blockers, and uncertainty without encouraging premature certainty.

Acceptance:

- no memory writes;
- no retrieval or bootstrap changes;
- no runtime policy mutation;
- each diagnostic cites its source artifact;
- every candidate remains `promotion_allowed=false`.

## Decision

Proceed with MMPO-inspired belief-clarity diagnostics before any new memory
runtime work.

Keep SuperLocalMemory as a borrow-pattern backlog:

- multi-channel contribution measurement;
- store-first pending/admission;
- mixed-precision metric research;
- explicit soft-prompt candidates.

No dependency adoption.
