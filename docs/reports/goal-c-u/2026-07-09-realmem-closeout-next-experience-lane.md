# RealMem Closeout and Next Experience Lane

Date: 2026-07-09

Source base commit: `5a4818a4`

Run type: docs-only closeout and next-lane selection, no runner

Memory evolution stage:

```yaml
memory_evolution_stage: reflection
experience_candidate_surface: next_lane_selection_only
runtime_authority: none
promotion_allowed: false
private_memory_export_allowed: false
third_party_runtime_dependencies: false
no_write_invariant: true
may_write_memory_now: false
may_change_retrieval_order_now: false
```

AB planning anchors:

- Durable memory key: `realmem_closeout_next_experience_lane_20260709`
- Work-memory key: `codex-realmem-closeout-next-experience-lane-20260709_active`
- Forum thread: `design#119`, post `2989`
- Parent reports:
  - `docs/reports/goal-c-u/2026-07-09-realmem-resolved-projection-gate.md`
  - `docs/reports/goal-c-u/2026-07-09-memory-survey-next-benchmark-retriage.md`
- Parent durable memory key: `realmem_resolved_projection_gate_20260709`

## Decision

```yaml
realmem_local_adapter_chain_status: closed_local_gate
realmem_real_runner_gate: owner_gated_boundary_packet_only
selected_next_lane: memoryarena_task_shape_packet
fallback_next_lane: ama_bench_interface_shape_packet
selected_next_lane_stage: experience_candidate
selection_reason: "MemoryArena is the lightest second-wave Experience benchmark after RealMem because it tests interdependent subtasks and memory-guided action from public JSONL rows without importing a runner."
benchmark_performance_claim_allowed: false
official_runner_import_allowed_now: false
dependency_install_allowed_now: false
private_memory_export_allowed: false
writes_ab_store: false
```

Close the RealMem local adapter chain at `realmem_resolved_projection_gate`.

The RealMem chain now has local, no-write coverage for:

- source-shape inspection;
- temporary adapter projection;
- reference resolution;
- final resolved projection gate.

The last gate accepted the pinned sample projection:

```yaml
projected_record_count: 2060
adapter_accepted_edge_count: 2703
resolver_added_memory_used_edges: 327
resolver_added_fallback_source_turn_edges: 30
final_accepted_edge_count: 3060
accepted_projection_item_count: 5120
residual_unresolved_count: 7
residual_unresolved_allowed_reason: source_turn_negative_only
```

That is enough local value for RealMem until a separate owner decision asks for
benchmark scores. RealMem official-runner work would cross dependency,
generation, evaluator, API, and score-semantics boundaries, so it should start
only as `realmem_real_runner_boundary_packet`.

Select `memoryarena_task_shape_packet` as the next Experience lane.
Keep `ama_bench_interface_shape_packet` as the fallback and likely follow-up.

## Source Snapshot

Observed on 2026-07-09 with bounded official source reads. These checks are
source-shape and license evidence, not benchmark performance evidence.

GitHub REST API reads for `AMA-Bench/AMA-Bench` were rate-limited from this
network path during this pass, so the current repo signal used `git ls-remote`
plus raw GitHub file checks instead.

| Candidate | Current source signal | Adapter value | Risk / hold reason | Verdict |
| --- | --- | --- | --- | --- |
| MemoryArena | Hugging Face dataset `ZexueHe/memoryarena`, API `sha=da1a37c8b19280e18627ca01cf368195a5e1d92e`, `lastModified=2026-03-03T00:39:50.000Z`, `downloads=15828`, `likes=14`, 8 siblings, 5 JSONL files. Dataset page reports 701 rows and 12.3 MB. Dataset card/project page states CC-BY-4.0. | Strong next Experience candidate. It tests whether memory from earlier subtasks is used to solve later subtasks across web navigation, planning, search, and formal reasoning shapes. | HF API tags currently omit a `license:` tag, even though the dataset page/license section states CC-BY-4.0. Record this mismatch and verify the page/license text in the next packet before any broader reuse. | **P0 next lane** |
| AMA-Bench | GitHub `AMA-Bench/AMA-Bench` main resolved by `git ls-remote` to `ddfd319e0be33424288c13806f1eafc63e625b59`; raw `LICENSE`, `README.md`, `requirements.txt`, `scripts/evaluate.sh`, and `src/evaluate.py` exist; raw license is MIT. Hugging Face dataset `AMA-bench/AMA-bench`, API `sha=a5777378066f53229a94557a7b192435cd027909`, `lastModified=2026-06-08T05:40:25.000Z`, `downloads=282`, `likes=9`, license `mit`, 4 siblings, `test/open_end_qa_set.jsonl`. | Strong long-horizon agentic memory candidate with trajectory plus QA structure and explicit recall/causal/state categories. | Heavier than MemoryArena for the next small packet because the repo exposes run/evaluate scripts, LLM-as-judge scoring, vLLM/API surfaces, and trajectory-level answer generation/evaluation boundaries. | P1 follow-up |

External source links checked:

- MemoryArena paper: https://arxiv.org/abs/2602.16313
- MemoryArena project page: https://memoryarena.github.io/
- MemoryArena dataset: https://huggingface.co/datasets/ZexueHe/memoryarena
- AMA-Bench paper: https://arxiv.org/abs/2602.22769
- AMA-Bench repository: https://github.com/AMA-Bench/AMA-Bench
- AMA-Bench dataset: https://huggingface.co/datasets/AMA-bench/AMA-bench

### MemoryArena Shape Notes

The MemoryArena dataset exposes five JSONL siblings:

```yaml
jsonl_siblings:
  - bundled_shopping/data.jsonl
  - formal_reasoning_math/data.jsonl
  - formal_reasoning_phys/data.jsonl
  - group_travel_planner/data.jsonl
  - progressive_search/data.jsonl
```

Bounded first-row shape checks:

```yaml
bundled_shopping/data.jsonl:
  keys: [answers, category, id, questions]
  question_count: 6
  answer_count: 6
  background_type: null
progressive_search/data.jsonl:
  keys: [answers, id, questions]
  question_count: 9
  answer_count: 9
  background_type: null
group_travel_planner/data.jsonl:
  keys: [answers, base_person, id, questions]
  question_count: 8
  answer_count: 8
  background_type: null
formal_reasoning_math/data.jsonl:
  keys: [answers, backgrounds, id, paper_name, questions]
  question_count: 5
  answer_count: 5
  background_type: list
  background_list_count: 5
formal_reasoning_phys/data.jsonl:
  keys: [answers, backgrounds, id, paper_name, questions]
  question_count: 3
  answer_count: 3
  background_type: list
  background_list_count: 3
```

This is the right next shape because it can be inspected as a bounded, public,
task-local JSONL corpus. A packet can project each task into temporary rows:

- task records;
- subtask question records;
- answer/reference records;
- optional background records;
- sequence edges between subtasks;
- support edges from background/base-person fields to subtasks;
- no runtime answer generation.

### AMA-Bench Shape Notes

The AMA-Bench Hugging Face sample exposes:

```yaml
dataset_path: test/open_end_qa_set.jsonl
sample_keys:
  - domain
  - episode_id
  - num_turns
  - qa_pairs
  - success
  - task
  - task_type
  - total_tokens
  - trajectory
sample_domain: Game
has_trajectory_like_key: true
license: MIT
```

This is valuable but heavier. A proper AMA-Bench packet should decide whether
AB is shaping:

- the full trajectory stream;
- a memory-construction interface;
- the QA retrieval/evaluation interface;
- or all three with strict no-runner boundaries.

That interface question is larger than the MemoryArena task-shape packet.

## Why MemoryArena Next

MemoryArena has the best marginal value after RealMem because it changes the
question being tested.

RealMem tested whether AB can map long persona dialogues, extracted memory
items, and memory-use references into a coherent temporary graph. MemoryArena
tests whether earlier task interactions and background state can be modeled as
experience that later subtasks depend on.

That maps to AB's next Experience-stage design questions:

- how to represent a task-local memory trajectory without promoting runtime
  rules;
- how to keep subtask order and interdependence explicit;
- how to distinguish background evidence from generated answers;
- how to build temporary records and edges without writing the real AB store;
- how to prepare for later action-quality analysis without making a score
  claim.

MemoryArena is also smaller and cleaner for the next no-write packet. It can be
handled with a docs-first shape contract plus a standard-library inspector
against public JSONL rows. AMA-Bench remains important, but it is a better
second step after AB has one interdependent-task shape packet in place.

## Next Work Packet

Name: `memoryarena_task_shape_packet`

Type: docs-first packet plus optional standard-library inspector.

Scope:

1. Verify MemoryArena dataset identity, paper link, project page, license text,
   API `sha`, and five JSONL siblings.
2. Inspect bounded rows from all five configs without cloning, installing
   dependencies, or using the Hugging Face `datasets` package.
3. Define a privacy-safe local contract:
   - dataset config;
   - task id;
   - ordered subtask questions;
   - ordered answers;
   - optional `backgrounds`;
   - optional `base_person`;
   - optional category or paper metadata.
4. Map the shape to temporary AB projection rows:
   - task `MemoryRecord` candidates;
   - subtask `MemoryRecord` candidates;
   - answer/reference `MemoryRecord` candidates;
   - background/base-person `MemoryRecord` candidates;
   - sequence, support, and answer-link `MemoryEdge` candidates.
5. Pre-register local-only checks:
   - schema/version fields;
   - config coverage;
   - question/answer length alignment;
   - background alignment when present;
   - no-write proof;
   - no benchmark-performance claim.

Admission bar:

- no dependency installation;
- no MemoryArena runner or environment harness;
- no API-key-backed generation or judging;
- no private AB memory export;
- no AB store writes;
- no benchmark score or performance claim;
- no MCP tool, DB schema, daemon, retrieval, consolidation, trigger-recall,
  bootstrap, or workflow-feedback runtime change.

## Deferred Lane

`ama_bench_interface_shape_packet` should remain queued after MemoryArena.

Admission criteria for that packet:

- keep GitHub code use at raw metadata/README/interface review unless a later
  owner gate permits runner work;
- verify repo HEAD, MIT license, dataset license, and `test/open_end_qa_set.jsonl`;
- decide whether AB models trajectories, QA pairs, memory-construction
  interfaces, or retrieval/evaluation interfaces;
- keep LLM-as-judge and vLLM/API paths out of scope until a runner boundary
  packet exists.

## Boundary

This packet did not:

- clone, vendor, import, or execute MemoryArena or AMA-Bench code;
- install Python, Rust, npm, Docker, Hugging Face, vLLM, or system dependencies;
- run MemoryArena, AMA-Bench, or RealMem evaluation;
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
bash -n scripts/verify-realmem-closeout-next-experience-lane.sh
scripts/verify-realmem-closeout-next-experience-lane.sh
git diff --check
```

The verifier asserts:

- RealMem local gate closure and pinned projection counts;
- selected/fallback next lanes;
- MemoryArena and AMA-Bench source anchors;
- MemoryArena five-config shape observations;
- AMA-Bench trajectory/QA shape observations;
- no-runner/no-dependency/no-write/no-score boundaries.

## Next Step

Proceed with `memoryarena_task_shape_packet` as a no-write packet. Do not run
MemoryArena, AMA-Bench, or RealMem evaluation, and do not install dependencies,
before that packet exists.
