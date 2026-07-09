# Memory Survey Next Benchmark Lane Retriage

Date: 2026-07-09

Source base commit: `076be559`

Run type: docs-only benchmark-lane selection, no runner

Memory evolution stage:

```yaml
memory_evolution_stage: reflection
runtime_authority: none
promotion_allowed: false
private_memory_export_allowed: false
third_party_runtime_dependencies: false
no_write_invariant: true
may_write_memory_now: false
may_change_retrieval_order_now: false
```

AB planning anchors:

- Durable memory key: `memory_survey_next_benchmark_retriage_20260709`
- Work-memory key: `codex-memory-survey-next-benchmark-retriage-20260709_active`
- Forum thread: `design#119`, post `2979`
- Parent reports:
  - `docs/reports/goal-c-u/2026-07-09-memory-survey-benchmark-triage.md`
  - `docs/reports/goal-c-u/2026-07-09-structmemeval-next-lane-value-assessment.md`
- Parent durable memory key: `structmemeval_next_lane_value_assessment_20260709`

## Decision

```yaml
structmemeval_status: locally_scaffolded
selected_next_lane: realmem_dialogue_shape_packet
selected_next_lane_stage: reflection_to_experience_candidate
selected_next_lane_reason: "RealMem adds multi-session continuity and query/use evidence not covered by StructMemEval accounting."
benchmark_performance_claim_allowed: false
realmem_runner_allowed_now: false
official_runner_import_allowed_now: false
dependency_install_allowed_now: false
private_memory_export_allowed: false
writes_ab_store: false
```

Select `realmem_dialogue_shape_packet` as the next no-write benchmark lane.

StructMemEval remains valuable, but the local accounting chain has already
created a strong structured-memory guardrail. RealMem now has the highest
marginal value because it stresses long-term continuity across many sessions,
query turns, and extracted memory points. That fills a gap left by the
StructMemEval accounting lane without requiring AB to export private memory or
run an external benchmark.

## Source Snapshot

Observed on 2026-07-09 with bounded GitHub/Hugging Face API reads and one raw
RealMem sample read. These checks are source-shape evidence, not benchmark
performance evidence.

| Candidate | Current source signal | Adapter value | Risk / hold reason | Retriage verdict |
| --- | --- | --- | --- | --- |
| RealMem | `AvatarMemory/RealMemBench`, default branch `main`, `pushed_at=2026-04-07T04:42:17Z`, license `Apache-2.0`, 82 tree paths, raw persona JSON under `dataset/`, `requirements.txt`, and `eval/` present | Strong continuity proxy for AB bootstrap, work memory, and project-state retrieval | Official eval path uses dependencies and API-key-backed generation/evaluation; do not run it now | **P0 next lane** |
| Memory Probe | `boqiny/memory-probe`, license API null, no license path, 29 tree paths, `data/locomo10.json`, `probes/`, `retrieval/`, `strategies/`, `requirements.txt` present | Excellent retrieval-vs-utilization diagnostic framing | `license unconfirmed`; README requires `OPENAI_API_KEY`; no code/data reuse until clarified | P1 concept-only reference |
| MemoryArena | `ZexueHe/memoryarena`, HF dataset last modified `2026-03-03T00:39:50Z`, 8 sibling files; rows expose `id`, `questions`, `answers`, and `backgrounds` | Strong Experience candidate with interdependent subtasks | Adapter must sequence subtasks and preserve task-local state; license metadata should be rechecked before code/data ingestion | P1 after RealMem |
| AMA-Bench | `AMA-Bench/AMA-Bench`, default branch `main`, `pushed_at=2026-06-15T01:22:27Z`, license `MIT`, 78 tree paths; HF dataset `AMA-bench/AMA-bench` license `mit` with `test/open_end_qa_set.jsonl` | Strong long-horizon agentic memory candidate; explicit two-stage memory interface | Heavier runner surface; README requires Python env and recommends CUDA/GPU; more likely to cross dependency/runtime boundaries | P1/P2 owner-gated design |
| MemoryBench | `THUIR/MemoryBench`, default branch `main`, `pushed_at=2026-06-27T04:24:37Z`, license `MIT`, 16425 tree paths; HF full dataset license `mit` with 211 siblings | Broad continual-learning and user-feedback signal | Very broad repo, many baselines, upstream baseline licenses, provider integrations, and result surfaces | P2 later |
| LifelongAgentBench | `caixd-220529/LifelongAgentBench`, license API null, no license path, 770 tree paths; HF dataset has `db_bench`, `knowledge_graph`, and `os_interaction` parquet files | Conceptually relevant lifelong-learning benchmark | `license unconfirmed`; setup uses Docker/MySQL/Ubuntu-style environments and distributed controller paths | Watchlist |

RealMem sample checked:

```yaml
source_url: https://raw.githubusercontent.com/AvatarMemory/RealMemBench/main/dataset/Lin_Wanyu_dialogues_256k.json
person_name: Lin_Wanyu
total_sessions: 207
total_tokens: 227417
dialogues_count: 207
extracted_memory_count: 443
query_turn_count: 126
query_with_memory_refs_count: 0
observed_turn_keys:
  - category_name
  - content
  - is_query
  - memory_session_uuids
  - memory_used
  - query_id
  - session_type
  - speaker
  - topic
```

Interpretation: RealMem has enough visible structure for a local shape packet.
The next step should inspect schemas and counts, not run RealMem generation,
retrieval, or evaluation code.

## Why RealMem Next

RealMem complements the StructMemEval chain instead of repeating it.

StructMemEval accounting tested whether a structured synthetic task can be
projected into a local no-write adapter and compared deterministically. RealMem
tests a different AB question: can a memory system preserve continuity across a
long persona trajectory with many sessions, extracted memory entries, and query
turns?

That maps to AB surfaces already under active design:

- bootstrap and project-continuity recall;
- `work_memory` continuity handoff;
- temporary `MemoryRecord` views for session turns and extracted memories;
- temporary `MemoryEdge` views for session chronology, source-turn linkage, and
  query-to-memory evidence;
- recall diagnostics that separate retrieval availability from answer use.

RealMem also keeps the first implementation surface small. A shape packet can
read one pinned raw JSON file, verify top-level fields and counts, and define an
adapter contract without installing dependencies, calling an LLM, writing AB
state, or making a benchmark claim.

## Next Work Packet

Name: `realmem_dialogue_shape_packet`

Type: docs-first packet plus optional standard-library inspector.

Scope:

1. Verify RealMem repository identity, license, default branch, and pinned raw
   sample URL.
2. Inspect one persona JSON shape without cloning or installing dependencies.
3. Define a privacy-safe local contract:
   - persona metadata;
   - chronological session rows;
   - dialogue turn rows;
   - extracted memory rows;
   - query turn rows;
   - optional `memory_used` / `memory_session_uuids` reference fields.
4. Map the shape to temporary AB projection rows:
   - `MemoryRecord` candidates for turns and extracted memories;
   - `MemoryEdge` candidates for chronology, source-turn, and query-evidence
     links;
   - no writes to the real AB store.
5. Pre-register local-only checks:
   - schema/version fields;
   - session count;
   - extracted-memory count;
   - query-turn count;
   - no-write proof;
   - no benchmark-performance claim.

Admission bar:

- no dependency installation;
- no RealMem official eval runner;
- no API-key-backed generation or judging;
- no private AB memory export;
- no AB store writes;
- no benchmark score or performance claim;
- no MCP tool, DB schema, daemon, retrieval, consolidation, trigger-recall,
  bootstrap, or workflow-feedback runtime change.

## Deferred Lanes

Memory Probe should remain a design reference for retrieval-vs-utilization
diagnostics, but not a code or data source while its license is unconfirmed.

MemoryArena and AMA-Bench are the best second-wave Experience candidates. They
should follow once AB has a clearer read-only trajectory adapter pattern from
RealMem.

MemoryBench and LifelongAgentBench should remain later lanes. MemoryBench is
well licensed at the repo level, but its breadth and baseline-license surface
are too large for the next small packet. LifelongAgentBench is blocked by
license uncertainty and interactive environment cost.

## Boundary

This assessment did not:

- clone, vendor, import, or execute any external benchmark code;
- install Python, Rust, npm, Docker, or system dependencies;
- run RealMem, Memory Probe, MemoryArena, AMA-Bench, MemoryBench, or
  LifelongAgentBench;
- call an LLM or API-key-backed evaluator;
- export private AB memory data;
- write to the AB memory store;
- add a DB schema, MCP tool, feature flag, or runtime process;
- change retrieval, bootstrap, consolidation, trigger-recall, workflow-feedback,
  forum status, or daemon configuration;
- claim benchmark score, benchmark accuracy, or benchmark performance.

## Verification

Commands:

```bash
bash -n scripts/verify-memory-survey-next-benchmark-retriage.sh
scripts/verify-memory-survey-next-benchmark-retriage.sh
git diff --check
```

The verifier asserts the selected lane, source-observation anchors, candidate
coverage, and no-runner/no-dependency/no-write/no-score boundaries.

## Next Step

Proceed with `realmem_dialogue_shape_packet` as a no-write packet. Do not run
RealMem evaluation or install its dependencies before that packet exists.
