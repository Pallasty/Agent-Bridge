# LLM Agent Memory Survey - Agent-Bridge Mapping

Date: 2026-07-09

Role: external research synthesis / Agent-Bridge planning anchor

External sources:

- Paper: https://arxiv.org/abs/2605.06716
- Paper HTML: https://arxiv.org/html/2605.06716
- Curated repository: https://github.com/FeishuLuo/Evolving-LLM-Agent-Memory-Survey

Local anchors:

- `docs/design/MEMORY_CONTINUITY_COGNITIVE_ARCHITECTURE_2026_06_19.md`
- `docs/design/MEMORY_CONTINUITY_IMPLEMENTATION_REVIEW_2026_06_19.md`
- `docs/design/WORKFLOW_FEEDBACK_LOOP_RESEARCH_2026_06_30.md`
- `docs/design/DESIGN-outcome-gated-consolidation-2026-06-28.md`
- `crates/bridge/src/workflow_feedback.rs`
- `crates/bridge/src/mcp_tools.rs`

## Verdict

Adopt this work as a taxonomy and benchmark watchlist, not as a code dependency.

The survey is directly relevant to Agent-Bridge because it frames LLM-agent
memory evolution as:

- Storage: trajectory preservation.
- Reflection: trajectory refinement.
- Experience: trajectory abstraction.

That maps cleanly onto AB's current direction. AB already has mature Storage,
usable Reflection surfaces, and early Experience candidates. The next valuable
move is not a new memory engine or a repo import. It is a report-first
classification and benchmark triage layer that lets AB evaluate whether its
existing feedback, consolidation, workflow-feedback, and trigger-recall surfaces
are moving from Reflection toward Experience without silently self-modifying
runtime policy.

Recommended posture: **ADOPT_AS_FRAMEWORK_AND_WATCHLIST**.

## Source Snapshot

The paper is `From Storage to Experience: A Survey on the Evolution of LLM
Agent Memory Mechanisms`, arXiv `2605.06716`, submitted 2026-05-07 and marked
as accepted by ACL 2026 Findings. Its central claim is that LLM-agent memory
research has split between engineering and cognitive-science traditions, and
needs a unified evolutionary framework.

The paper's three drivers are:

- long-range consistency;
- dynamic environments;
- continual learning.

The paper's frontier Experience mechanisms are:

- active exploration;
- cross-trajectory abstraction.

The paper's future directions are especially relevant to AB:

- dynamic memory triggering based on task type;
- working memory;
- richer Experience-stage datasets and benchmarks;
- distributed shared memory;
- multimodal memory.

The GitHub repository is a curated paper and benchmark index for the survey,
not an implementation library. The README currently describes 140+ papers and
40+ benchmarks, including Storage, Reflection, and Experience stage benchmark
sections.

## AB Stage Mapping

| Survey stage | AB equivalents | Current read |
| --- | --- | --- |
| Storage | `MemoryRecord`, `MemoryEdge`, SQLite store, FTS/semantic/hybrid retrieval, scopes, tags, importance, status, work memory, forum/sync mirrors, `present_outcome` rows | Strong. AB has durable storage, graph topology, retrieval, lifecycle, sync, and active scratch surfaces. |
| Reflection | `memory_retrieval_feedback`, `memory_consolidation_queue`, `memory_correction`, `session_reflect`, present-outcome ingestion, workflow-feedback reports, neural/BioCortex shadow evaluation | Mid to strong. AB can record retrieval outcomes, surface stale/duplicate/harmful/too-large candidates, and produce reviewable lessons. Many paths are intentionally read-only or dry-run-first. |
| Experience | `agent_bridge.experience.v0`, workflow-feedback promotion gates, outcome-gated consolidation ladder, trigger-recall opt-in ladder, explicit skill/runbook candidates, cross-session reports | Early. AB has the right shape for Experience, but should keep it explicit, evidence-linked, and owner-gated before any runtime influence. |

The survey validates AB's existing bias: preserve raw trace, reflect into
reviewable lessons, and only promote generalized behavior after evidence.
Experience should mean compressed, reusable rules with provenance, not silent
retrieval mutation or automatic profile/skill rewriting.

## Useful Borrow Candidates

### 1. Add a survey-stage lens to AB reports

First slice: docs/report only.

Add a small `memory_evolution_stage` field or section to future research and
workflow-feedback reports:

- `storage`
- `reflection`
- `experience_candidate`
- `experience_promoted`

Do not add a DB column yet. The field can be a report convention until we prove
that it is queried often enough to deserve schema support.

### 2. Build a benchmark watchlist

The repository's benchmark section is useful as a triage source. Highest-fit
benchmarks to inspect first:

- `RealMem`: real-world, project-oriented memory.
- `StructMemEval`: memory structure organization.
- retrieval-vs-utilization diagnostics: separates failure to retrieve from
  failure to use retrieved memory.
- `MemoryArena`: interdependent multi-session agentic tasks.
- `AMA-Bench`: long-horizon agentic memory.
- `MemoryBench` / `LifelongAgentBench`: continual-learning framing.

Next step should be a bounded benchmark-fit report, not immediate benchmark
integration. Each benchmark needs license, data shape, task grain, and whether
it can run against AB without leaking private local memory.

### 3. Start Experience as explicit rule candidates

AB already has enough material for cross-trajectory abstraction:

- retrieval feedback outcomes;
- consolidation queue candidates;
- workflow-feedback reports;
- present outcomes;
- session reflection lessons;
- tool telemetry and failure classifications.

First Experience pilot should produce explicit rule candidates such as:

```json
{
  "schema": "agent_bridge.experience_rule_candidate.v0",
  "source_trajectories": ["..."],
  "rule": "When a memory is stale twice from distinct sources and has no positive retrieval use, propose archival through the outcome-gated ladder.",
  "evidence_summary": "...",
  "counterexamples": ["..."],
  "promotion_allowed": false
}
```

It should write no memory and change no ranking by default. Promotion belongs
behind the existing owner-review and gate patterns.

### 4. Use task-type dynamic triggering as a read-only diagnostic

The survey calls out dynamic triggering by task type. AB already has continuity
roles and trigger-recall opt-in surfaces. The conservative next step is a
read-only diagnostic that classifies requests into memory trigger classes:

- active state;
- constraint;
- procedure;
- evidence;
- preference;
- stale/conflict check;
- archive lookup.

The diagnostic should report what it would ask memory for and compare that to
what actually entered context. It should not change `memory_search`,
`session_bootstrap`, or trigger-recall defaults.

### 5. Treat distributed and multimodal memory as watch areas

Distributed shared memory maps to AB's forum/sync/cross-machine state. Multimodal
memory maps to present/outcome, voice/avatar, desktop/vision, and semantic-event
lanes. These are relevant but not the highest near-term leverage. Use the survey
as framing while AB keeps the current report-first and gate-first discipline.

## Anti-Goals

Do not:

- clone or vendor the curated repository as a runtime dependency;
- add a new memory engine because the survey exists;
- add a `memory_stage` DB column before report usage proves it useful;
- let Experience-stage summaries silently rewrite `AGENT.md`, skills, prompts,
  retrieval order, or consolidation behavior;
- fine-tune or internalize memory behavior from private AB trajectories without
  a separate privacy, evaluation, rollback, and owner-approval design;
- treat benchmark names in the curated README as evidence that AB passes or
  fails anything before running a local fit check.

## Proposed Next Slice

Name: `survey_stage_benchmark_triage`

Type: docs/report first, no runtime changes.

Scope:

1. Create a compact benchmark-fit matrix for the top 5-7 benchmark candidates.
2. Add a `Storage / Reflection / Experience` classification rubric for AB
   memory reports.
3. Pick one local Experience candidate surface to prototype as read-only JSON:
   cross-trajectory rule candidates from existing feedback and workflow reports.

Acceptance:

- no code path changes retrieval, bootstrap, consolidation, forum, or memory
  writes;
- every selected benchmark has a source URL, license note, data availability
  note, and AB fit verdict;
- any Experience candidate includes source trajectory IDs, counterexamples or
  blockers, and `promotion_allowed=false`.

## Current Decision

This survey strengthens the existing Agent-Bridge memory direction:

```text
trace -> feedback/outcome -> reflection -> explicit rule candidate ->
held-out/shadow evidence -> owner gate -> optional promotion
```

The highest-value next move is to make this ladder easier to evaluate and
explain, not to accelerate runtime mutation.
