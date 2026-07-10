# MemoryArena Task Shape Packet

Date: 2026-07-09

Source base commit: `638a7896`

Run type: local MemoryArena task-shape inspection, no runner

Memory evolution stage:

```yaml
memory_evolution_stage: experience_candidate
stage_reason: "Models interdependent task-local memory trajectories as temporary projection candidates without promoting runtime behavior."
runtime_authority: none
promotion_allowed: false
private_memory_export_allowed: false
third_party_runtime_dependencies: false
no_write_invariant: true
may_write_memory_now: false
may_change_retrieval_order_now: false
```

AB planning anchors:

- Durable memory key: `memoryarena_task_shape_packet_20260709`
- Work-memory key: `codex-memoryarena-task-shape-packet-20260709_active`
- Forum thread: `design#119`, post `2992`
- Parent report:
  `docs/reports/goal-c-u/2026-07-09-realmem-closeout-next-experience-lane.md`
- Parent durable memory key: `realmem_closeout_next_experience_lane_20260709`

External anchors:

- Paper: https://arxiv.org/abs/2602.16313
- Project page: https://memoryarena.github.io/
- Dataset: https://huggingface.co/datasets/ZexueHe/memoryarena
- Observed Hugging Face revision:
  `da1a37c8b19280e18627ca01cf368195a5e1d92e`
- Observed API metadata:
  `lastModified=2026-03-03T00:39:50.000Z`, `downloads=15828`,
  `likes=14`
- Observed license: CC-BY-4.0 on the project page. The Hugging Face API tags
  omit a `license:` tag during this pass, so page/license text remains the
  license anchor for this packet.

## Verdict

`memoryarena_task_shape_packet` is implemented as a standard-library helper
and offline verifier.

The helper reads five public JSONL configs from the pinned Hugging Face
revision, validates task-local sequence shape, and emits a redacted packet with
temporary AB-like projection counts.

This is not a MemoryArena benchmark score.

## Landed Files

```text
scripts/memoryarena-task-shape-inspector.py
scripts/verify-memoryarena-task-shape-packet.sh
docs/reports/goal-c-u/2026-07-09-memoryarena-task-shape-packet.md
```

## Packet Schema

```yaml
schema: agent_bridge.memoryarena_task_shape_packet.v0
source_dataset: https://huggingface.co/datasets/ZexueHe/memoryarena
source_project: https://memoryarena.github.io/
source_paper: https://arxiv.org/abs/2602.16313
source_revision: da1a37c8b19280e18627ca01cf368195a5e1d92e
official_runner_import_allowed: false
memoryarena_runner_allowed_now: false
third_party_runtime_dependencies: false
api_key_required: false
private_memory_export_allowed: false
writes_ab_store: false
benchmark_performance_claim: false
raw_content_in_output: false
```

Default source behavior:

- no source directory: read the pinned Hugging Face revision;
- `--source-dir`: read local `<config>/data.jsonl` files for offline fixtures;
- no Hugging Face `datasets` package;
- no MemoryArena code import;
- no dependency installation;
- no raw question, answer, background, base-person, category, or paper content
  emitted.

## Observed Full-Shape Result

Command shape:

```bash
scripts/memoryarena-task-shape-inspector.py --output "$tmpdir/memoryarena.json"
```

Observed result:

```yaml
total_rows: 701
config_count: 5
question_count: 4850
answer_count: 4850
background_slot_count: 440
nonempty_background_count: 132
empty_background_count: 308
base_person_count: 270
answer_value_shapes:
  object: 900
  array: 1869
  string: 2081
base_person_value_shapes:
  object: 270
qa_length_mismatch_count: 0
background_length_mismatch_count: 0
temporary_record_count: 10808
temporary_edge_count: 14952
accepted_projection_item_count: 25760
```

Config-level observations:

```yaml
bundled_shopping:
  row_count: 150
  keys: [answers, category, id, questions]
  answer_value_shapes:
    object: 900
  question_count_distribution:
    6: 150
  answer_count_distribution:
    6: 150
  background_count_distribution:
    absent: 150
  qa_length_mismatch_count: 0
group_travel_planner:
  row_count: 270
  keys: [answers, base_person, id, questions]
  answer_value_shapes:
    array: 1869
  base_person_value_shapes:
    object: 270
  question_count_distribution:
    5: 37
    6: 47
    7: 86
    8: 100
  answer_count_distribution:
    5: 37
    6: 47
    7: 86
    8: 100
  background_count_distribution:
    absent: 270
  base_person_count: 270
  qa_length_mismatch_count: 0
progressive_search:
  row_count: 221
  keys: [answers, id, questions]
  answer_value_shapes:
    string: 1641
  question_count_distribution:
    4: 7
    5: 30
    6: 42
    7: 45
    8: 45
    9: 20
    10: 13
    11: 11
    12: 4
    13: 1
    14: 2
    16: 1
  answer_count_distribution: same_as_question_count_distribution
  background_count_distribution:
    absent: 221
  qa_length_mismatch_count: 0
formal_reasoning_math:
  row_count: 40
  keys: [answers, backgrounds, id, paper_name, questions]
  answer_value_shapes:
    string: 354
  background_value_shapes:
    string: 354
  question_count_distribution:
    2: 1
    4: 1
    5: 3
    6: 4
    7: 6
    8: 5
    9: 5
    10: 3
    11: 4
    12: 2
    13: 3
    14: 1
    15: 1
    16: 1
  answer_count_distribution: same_as_question_count_distribution
  background_count_distribution: same_as_question_count_distribution
  background_slot_count: 354
  nonempty_background_count: 112
  empty_background_count: 242
  background_length_mismatch_count: 0
formal_reasoning_phys:
  row_count: 20
  keys: [answers, backgrounds, id, paper_name, questions]
  answer_value_shapes:
    string: 86
  background_value_shapes:
    string: 86
  question_count_distribution:
    2: 2
    3: 8
    4: 6
    5: 1
    8: 1
    9: 1
    12: 1
  answer_count_distribution: same_as_question_count_distribution
  background_count_distribution: same_as_question_count_distribution
  background_slot_count: 86
  nonempty_background_count: 20
  empty_background_count: 66
  background_length_mismatch_count: 0
```

Acceptance gates:

```yaml
schema_matches: true
source_revision_pinned: true
config_count_matches_expected: true
all_five_configs_present: true
question_answer_lengths_aligned: true
background_lengths_aligned_when_present: true
raw_content_redacted: true
no_ab_store_write: true
no_dependency_installation: true
no_runner_import: true
no_benchmark_performance_claim: true
```

## Temporary Projection Contract

The helper models MemoryArena as task-local temporary projection rows. These are
review candidates only; they are not inserted into the AB memory store.

Temporary record types:

```yaml
record_types:
  - config
  - task
  - subtask_question
  - answer_reference
  - background
  - base_person
```

Temporary edge types:

```yaml
edge_types:
  - config_contains_task
  - task_contains_question
  - question_precedes_question
  - question_answered_by
  - background_supports_question
  - base_person_supports_task
```

Projection meaning:

- `config` records keep the five dataset configs explicit;
- `task` records represent one JSONL row;
- `subtask_question` records represent ordered subtasks within a row;
- `answer_reference` records represent aligned answer references without using
  them as generated outputs. Their values may be strings, objects, or arrays
  depending on config, and the packet records shape only;
- `background` records represent aligned formal-reasoning context when present;
  empty background placeholders are counted as slots but are not projected as
  background records or support edges;
- `base_person` records represent group-travel persona constraints when present;
  values may be objects and are redacted to value-shape counts;
- sequence edges preserve subtask order;
- support edges preserve which background or persona state can influence the
  task or question.

This gives AB a no-write Experience candidate surface: it can reason about
interdependent task trajectories without promoting generalized runtime rules.

## Why This Is Useful After RealMem

RealMem established a local projection path for long persona dialogue memory,
extracted memory rows, and memory-use references. MemoryArena adds a different
stressor: task-local interdependence.

The shape packet lets AB test whether its adapter language can represent:

- ordered subtasks;
- later subtasks depending on earlier state;
- background support separated from answer references;
- persona or category fields as support context rather than runtime rules;
- temporary graph projection without store mutation.

The next layer can compare MemoryArena's task graph shape with RealMem's
dialogue graph shape before any benchmark runner is considered.

## Boundary

Admission bar preserved:

- no MemoryArena runner;
- no dependency installation;
- no API-key-backed generation or judging;
- no private AB memory export;
- no AB store writes;
- no benchmark score or performance claim.

This packet did not:

- clone, vendor, import, or execute MemoryArena code;
- install Python, Rust, npm, Docker, Hugging Face, browser, or system
  dependencies;
- run MemoryArena tasks, web navigation, planning, search, formal reasoning, or
  evaluation;
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
python3 -m py_compile scripts/memoryarena-task-shape-inspector.py
bash -n scripts/verify-memoryarena-task-shape-packet.sh
scripts/verify-memoryarena-task-shape-packet.sh
scripts/memoryarena-task-shape-inspector.py --output "$tmpdir/live.json"
git diff --check
```

The verifier uses an offline MemoryArena-shaped fixture and sentinel SQLite
store to assert:

- output schema, source anchors, and no-runner/no-dependency/no-API flags;
- all five configs are represented;
- question/answer and background alignment checks;
- temporary projection counts;
- no-write deltas;
- raw fixture content values are absent from output;
- report anchors and no-score/no-runtime boundaries.

## Next Step

Proceed with `memoryarena_adapter_contract`: turn the shape packet into a
stable local adapter contract that names temporary record IDs and edge IDs, then
compare that contract against the RealMem adapter family. Do not run
MemoryArena evaluation or install dependencies before that contract exists.
