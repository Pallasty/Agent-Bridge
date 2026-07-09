# Memory Survey Benchmark Triage

Date: 2026-07-09

Source base commit: `e0889519`

Run type: docs-only research triage

Parent design anchor:

- `docs/design/LLM_AGENT_MEMORY_SURVEY_AGENT_BRIDGE_MAPPING_2026_07_09.md`

External survey anchor:

- Paper: https://arxiv.org/abs/2605.06716
- Curated repo: https://github.com/FeishuLuo/Evolving-LLM-Agent-Memory-Survey

## Verdict

Actionable, but only as a report-first lane.

The next AB memory-evolution move should be:

1. classify future memory reports by `Storage / Reflection / Experience`;
2. shortlist external benchmarks by license, data shape, and AB adapter cost;
3. prototype Experience as explicit rule candidates with source evidence and
   `promotion_allowed=false`.

Do not integrate a benchmark runner or add new runtime memory behavior in this
slice.

## Boundary

This report:

- does not write memory, forum, or runtime state;
- does not add an MCP tool;
- does not change retrieval, bootstrap, consolidation, trigger-recall, or
  workflow-feedback behavior;
- does not clone or vendor an external benchmark repository.

## Benchmark Fit Matrix

| Candidate | Stage | Source | License note | Data availability | AB fit verdict |
| --- | --- | --- | --- | --- | --- |
| RealMem | Reflection / early Experience | Paper: https://arxiv.org/abs/2601.06966; repo: https://github.com/AvatarMemory/RealMemBench | Apache-2.0 shown on repo page | Repo exposes JSON dialogue datasets under `dataset/datasets/`; paper says 2,000+ cross-session dialogues across 11 scenarios | **P1 fit.** Good project-continuity proxy for AB bootstrap, work memory, and project-state retrieval. Needs adapter to map dialogue sessions to AB memories without importing private local state. |
| StructMemEval | Reflection | Paper: https://arxiv.org/abs/2602.11243; repo: https://github.com/yandex-research/StructMemEval | Apache-2.0 shown on repo page | Repo exposes raw benchmark data for accounting, tree-based, state-machine-location, and recommendations tasks | **P0 fit.** Strongest first external eval because it tests structured memory organization, matching AB graph/related-key/consolidation surfaces. Small quick-test path exists. |
| Memory Probe | Reflection diagnostic | Paper: https://arxiv.org/abs/2603.02473; repo: https://github.com/boqiny/memory-probe | `license_unconfirmed`: no `LICENSE` at raw main path and no license shown on repo page during this pass | Repo exposes `data`, `probes`, `retrieval`, and strategies; uses LoCoMo and LLM-as-judge probes | **P0/P1 conceptual fit, implementation held.** The retrieval-vs-utilization split maps directly to AB recall/retrieval feedback, but license must be clarified before code reuse. Reimplementing the diagnostic idea locally is safer than importing code. |
| MemoryArena | Experience | Paper: https://arxiv.org/abs/2602.16313; dataset: https://huggingface.co/datasets/ZexueHe/memoryarena | CC-BY-4.0 shown on Hugging Face dataset page | HF dataset has 701 rows, 12.3 MB, JSONL task rows with multi-subtask questions, answers, and backgrounds | **P1 fit.** Best agentic Experience benchmark candidate. It evaluates whether earlier interactions guide later subtasks. Adapter cost is higher because AB must run session sequences rather than static retrieval. |
| AMA-Bench | Experience | Paper: https://arxiv.org/abs/2602.22769; repo: https://github.com/AMA-Bench/AMA-Bench | MIT shown on repo page | Repo says Hugging Face dataset and leaderboard released; interface splits memory construction and retrieval | **P1 fit.** Strong long-horizon trajectory benchmark. Good for AB Experience Object and causality-graph questions, but heavier than StructMemEval because it expects trajectory construction/retrieval harness integration. |
| MemoryBench | Experience / continual learning | Paper: https://arxiv.org/abs/2510.17281; repo: https://github.com/THUIR/MemoryBench | MIT shown on repo page; upstream baselines keep their own licenses | Repo exposes lightweight interface, 28 datasets, 8 baselines, off-policy/on-policy regimes, HF full dataset/results links | **P2 fit.** Useful later for continual-learning framing, but too broad for first AB adapter. High dependency and evaluator surface. |
| LifelongAgentBench | Experience / lifelong learning | Paper: https://arxiv.org/abs/2505.11942; page: https://caixd-220529.github.io/LifelongAgentBench/; repo: https://github.com/caixd-220529/LifelongAgentBench; dataset: https://huggingface.co/datasets/csyq/LifelongAgentBench | `license_unconfirmed`: no `LICENSE` at raw main path and no clear license shown on repo/HF pages during this pass | HF dataset page shows 1,396 rows, 755 kB; repo requires Docker-style DB/OS environments for full runs | **Watchlist.** Conceptually relevant, but first AB pass should not depend on containerized interactive envs or unconfirmed license. |

## First Adapter Recommendation

Start with **StructMemEval** as the first external benchmark fit check.

Reasons:

- It is licensed clearly enough for local evaluation planning.
- It has raw benchmark data in-repo.
- It stresses structured memory, not just conversational recall.
- It can be evaluated without exposing AB's private memory store.
- It maps to existing AB surfaces: `MemoryRecord`, `MemoryEdge`,
  `memory_related_keys_*`, `memory_consolidation_queue`,
  `outcome_gated_consolidation_*`, and graph hygiene diagnostics.

The first adapter should be a design/report or local one-shot script proposal,
not a committed benchmark dependency. It should define:

- input rows;
- expected memory operations;
- output metrics;
- no-write mode;
- where AB is being tested: storage, reflection, or experience.

## Report Classification Rubric

Future AB memory reports should add a small classification block:

```yaml
memory_evolution_stage: reflection
stage_reason: "Evaluates retrieval feedback and consolidation candidates; does not promote generalized rules."
runtime_authority: none
promotion_allowed: false
source_evidence:
  - "agent_bridge.memory_consolidation_queue.v1"
  - "agent_bridge.workflow_feedback_report.v0"
```

Use these values:

| Value | Meaning | Required boundary |
| --- | --- | --- |
| `storage` | Preserves or audits raw/typed memory records and retrieval surfaces | No learned/generalized behavior claim. |
| `reflection` | Evaluates, corrects, labels, summarizes, or queues memory records | Must keep source evidence linkable and avoid default runtime influence unless separately gated. |
| `experience_candidate` | Abstracts a cross-trajectory rule, workflow, policy prior, or skill candidate | Must include source IDs, counterexamples/blockers, and `promotion_allowed=false`. |
| `experience_promoted` | A generalized rule has passed held-out/shadow evidence and owner gate | Must cite approval packet, rollback path, and post-promotion monitoring. |

Do not add this as a DB schema field yet. Keep it as report convention until it
appears in enough reports to justify structured indexing.

## Read-Only Experience Candidate Prototype

This is the candidate shape AB should prototype before any code path can promote
Experience-stage behavior:

```json
{
  "schema": "agent_bridge.experience_rule_candidate.v0",
  "memory_evolution_stage": "experience_candidate",
  "candidate_id": "exp_rule_outcome_gated_stale_archive_20260709_prototype",
  "source_trajectory_ids": [
    "docs:WORKFLOW_FEEDBACK_LOOP_RESEARCH_2026_06_30",
    "schema:agent_bridge.memory_consolidation_queue.v1",
    "schema:agent_bridge.outcome_gated_consolidation.status.v1",
    "schema:agent_bridge.workflow_feedback_report.v0"
  ],
  "rule": "When a memory receives stale feedback from at least two distinct sources, has no recent positive use signal, and is not a durable graph hub, propose archival through the existing outcome-gated consolidation ladder.",
  "evidence_summary": "AB already records retrieval feedback, emits consolidation gated_actions with blockers, and has a staged approval ladder for any mutation.",
  "counterexamples": [
    "A memory can be stale for one task but still useful in another scope.",
    "A stale target may be a durable hub whose edges make direct archival harmful.",
    "Sparse feedback can reflect query phrasing rather than memory quality."
  ],
  "blockers": [
    "needs held-out replay over historical feedback before any promotion",
    "needs positive-use veto threshold",
    "needs owner review packet and rollback path"
  ],
  "allowed_next_surface": "read_only_shadow_report",
  "promotion_allowed": false,
  "may_write_memory_now": false,
  "may_change_retrieval_order_now": false
}
```

This prototype deliberately points to existing AB schemas and docs instead of
inventing a new authority layer.

## Next Work Packet

Name: `structmemeval_fit_packet`

Type: design/report first.

Scope:

1. Inspect StructMemEval raw data shapes locally or from source.
2. Define a privacy-safe AB adapter contract that uses synthetic benchmark data
   only.
3. Map benchmark tasks to AB operations:
   - storage-only retrieval;
   - graph/structure-aided retrieval;
   - reflection/consolidation candidate generation.
4. Pre-register metrics:
   - task accuracy;
   - retrieval hit rate;
   - structure correctness;
   - token/context cost;
   - no-write invariant.

Admission bar before code:

- license checked from repository source;
- no private AB memory exported;
- first runner must be read-only;
- no benchmark package becomes a runtime dependency;
- `cargo test` is not required until a Rust adapter exists.

## Decision

Proceed toward StructMemEval first. Keep Memory Probe as a diagnostic design
reference, MemoryArena and AMA-Bench as second-wave Experience benchmarks, and
MemoryBench/LifelongAgentBench as later continual-learning watchlist items.
