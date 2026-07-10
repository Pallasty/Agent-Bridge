# MemoryArena Adapter Contract

Date: 2026-07-09

Source base commit: `b1cfd8f6`

Run type: no-write adapter contract implementation

Memory evolution stage:

```yaml
memory_evolution_stage: experience_candidate
experience_candidate_surface: adapter_contract_only
runtime_authority: none
promotion_allowed: false
private_memory_export_allowed: false
third_party_runtime_dependencies: false
no_write_invariant: true
may_write_memory_now: false
may_change_retrieval_order_now: false
```

AB planning anchors:

- Durable memory key: `memoryarena_adapter_contract_20260709`
- Work-memory key: `codex-memoryarena-adapter-contract-20260709_active`
- Forum thread: `design#119`, post `2994`
- Parent report:
  `docs/reports/goal-c-u/2026-07-09-memoryarena-follow-on-roadmap.md`
- Parent durable memory key: `memoryarena_follow_on_roadmap_20260709`

## Verdict

`memoryarena_adapter_contract` is implemented as a standard-library, no-write
adapter packet with deterministic temporary record and edge identifiers.

The full pinned public dataset passes count parity, identity uniqueness, edge
endpoint resolution, source-content redaction, and no-score gates. This is an
adapter-contract result, not a MemoryArena benchmark score.

Landed files:

```text
scripts/memoryarena-adapter-contract.py
scripts/verify-memoryarena-adapter-contract.sh
docs/reports/goal-c-u/2026-07-09-memoryarena-adapter-contract.md
```

## Packet Contract

```yaml
schema: agent_bridge.memoryarena_adapter_contract.v0
shape_schema: agent_bridge.memoryarena_task_shape_packet.v0
source_revision: da1a37c8b19280e18627ca01cf368195a5e1d92e
scope: benchmark:memoryarena
verdict: PASS
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

- no `--source-dir`: read the five JSONL files from the pinned Hugging Face
  revision;
- `--source-dir`: read local `<config>/data.jsonl` fixtures;
- `--store-db`: read only the `memories`, `memory_edges`, and
  `semantic_events` row counts before and after projection;
- no Hugging Face `datasets` package and no MemoryArena code import;
- output includes public config names, source digests, field shapes, counts,
  identifier templates, and one redacted sample per record/edge kind;
- output excludes raw source IDs, questions, answers, backgrounds,
  base-person values, categories, and paper names.

## Identifier Contract

Task identity is stable within the pinned source revision and does not depend
on JSONL row order.

```yaml
stability_scope: pinned_source_revision
task_identity_input: source_revision,config,canonical_json(source_id)
task_identity_digest: sha256_first_20_hex
edge_identity_input: logical_edge_kind,from_key,to_key
edge_identity_digest: sha256_first_24_hex
source_id_exposed: false
templates:
  config: "memoryarena:{config}:config"
  task: "memoryarena:{config}:task:{task_identity_digest}"
  question: "{task_key}:question:{one_based_ordinal_4d}"
  answer_reference: "{task_key}:answer:{one_based_ordinal_4d}"
  background: "{task_key}:background:{one_based_ordinal_4d}"
  base_person: "{task_key}:base-person"
  edge: "memoryarena:edge:{logical_edge_kind}:{edge_identity_digest}"
```

The task digest binds source revision, config, and canonical JSON source ID.
Ordered child keys preserve task-local sequence while avoiding question,
answer, background, or base-person content in the identifier. Edge IDs bind
the logical edge kind and both endpoint keys.

Duplicate source IDs within one config therefore produce duplicate task and
child IDs and fail the contract instead of being silently disambiguated by row
position. The offline verifier includes this rejection case.

## Full Pinned Result

Command shape:

```bash
scripts/memoryarena-adapter-contract.py --output "$tmpdir/live.json"
```

Observed projection:

```yaml
projected_record_count: 10808
unique_record_id_count: 10808
record_kind_counts:
  benchmark_synthetic_memoryarena_config: 5
  benchmark_synthetic_memoryarena_task: 701
  benchmark_synthetic_memoryarena_question: 4850
  benchmark_synthetic_memoryarena_answer_reference: 4850
  benchmark_synthetic_memoryarena_background: 132
  benchmark_synthetic_memoryarena_base_person: 270
accepted_memory_edge_count: 14952
unique_edge_id_count: 14952
accepted_logical_edge_counts:
  config_contains_task: 701
  task_contains_question: 4850
  question_precedes_question: 4149
  question_answered_by: 4850
  background_supports_question: 132
  base_person_supports_task: 270
accepted_projection_item_count: 25760
duplicate_record_id_count: 0
duplicate_edge_id_count: 0
dangling_edge_endpoint_count: 0
```

Shape parity remains:

```yaml
row_count: 701
question_count: 4850
answer_count: 4850
background_slot_count: 440
nonempty_background_count: 132
empty_background_count: 308
base_person_count: 270
answer_value_shapes:
  array: 1869
  object: 900
  string: 2081
base_person_value_shapes:
  object: 270
temporary_record_count: 10808
temporary_edge_count: 14952
```

Pinned per-config source digests:

```yaml
bundled_shopping: 4411a2da528a33dc6aca519b49cc225895363f18b2d19b191fddb501200134ef
formal_reasoning_math: ff5b0ad575847c7476a02d1e35661592a833bd0cff384cb54bc6f35b46de7803
formal_reasoning_phys: 580862006af2ff2bfc8c5d2d2b9a60bf33a46cbb64f27d60a2bfe039aec61cf6
group_travel_planner: 2f955d444f6f3ad3c5da2064359ab19f8fc1f90621ff9d00723a450a009c3732
progressive_search: b445ee36fa3ccb9ad08eae9e7adda86bbc64f14f1e2a0682a8b2085cdb8e4c0e
```

Empty formal-reasoning background placeholders remain counted as source slots
but are not assigned record or edge IDs. Heterogeneous answer and base-person
values are represented only by shape metadata in the packet.

Acceptance gates:

```yaml
source_revision_pinned: true
shape_schema_matches: true
all_five_configs_present: true
record_count_matches_shape_packet: true
edge_count_matches_shape_packet: true
record_ids_unique: true
edge_ids_unique: true
edge_endpoints_resolve: true
raw_content_redacted: true
no_ab_store_write: true
no_benchmark_performance_claim: true
```

## Adapter Family Comparison

The packet is structurally aligned with the existing RealMem no-write adapter
family without claiming runtime interchangeability.

```yaml
reference_schema: agent_bridge.realmem_adapter_contract.v0
memoryarena_reference_resolver_required: false
realmem_reference_resolver_required: true
compatible_no_write_adapter_structure: true
runtime_compatibility_claim: false
```

Shared surfaces:

- versioned adapter and source-shape schemas;
- benchmark-only scope, `PASS`/`FAIL` verdict, and explicit no-write/no-score
  flags;
- redacted record descriptors with key, kind, source path, tags, status,
  importance, and content-source policy;
- typed edge descriptors with endpoints, logical kind, source path, and
  weight;
- record/edge counts, acceptance gates, representative samples, and a
  SQLite row-count sentinel.

The source semantics differ. RealMem contains content/session references that
require a separate resolver before its final projection gate. MemoryArena's
accepted edges are derived from source-local config, task, ordinal, background,
and base-person positions, so this contract has no unresolved-reference lane.
That difference is explicit rather than flattened into a false shared runtime
model.

## Offline Verification

The fixture deliberately covers:

- object answers in bundled shopping;
- array answers and object `base_person` in group travel;
- string answers in progressive and formal reasoning;
- aligned non-empty and empty background slots;
- six record kinds and six edge kinds;
- a SQLite sentinel with one row in each protected table;
- a duplicate source-ID fixture that must return `FAIL`.

Fixture result:

```yaml
projected_record_count: 36
accepted_memory_edge_count: 36
accepted_projection_item_count: 72
duplicate_record_id_count: 0
duplicate_edge_id_count: 0
dangling_edge_endpoint_count: 0
sqlite_deltas:
  memories: 0
  memory_edges: 0
  semantic_events: 0
```

The duplicate fixture proves that repeated source identity is rejected by both
`record_ids_unique` and `edge_ids_unique` gates.

## Boundary

This packet performed:

- public JSONL reads from one pinned revision;
- standard-library parsing, hashing, validation, and temporary in-memory ID
  collection;
- redacted JSON packet output;
- offline SQLite before/after row-count checks.

It did not perform:

- no MemoryArena runner or environment harness;
- no dependency installation;
- no LLM or API-key-backed generation or judging;
- no private AB memory export;
- no AB store writes;
- no MCP tool, database schema, daemon, retrieval, bootstrap, consolidation,
  trigger-recall, or workflow-feedback change;
- no benchmark score or performance claim.

## Verification

Commands:

```bash
python3 -m py_compile \
  scripts/memoryarena-task-shape-inspector.py \
  scripts/memoryarena-adapter-contract.py
bash -n scripts/verify-memoryarena-adapter-contract.sh
scripts/verify-memoryarena-adapter-contract.sh
scripts/memoryarena-adapter-contract.py --output "$tmpdir/live.json"
git diff --check
```

Verified:

- Python compilation;
- verifier shell syntax;
- heterogeneous offline fixture and raw-content redaction;
- SQLite no-write sentinel;
- duplicate source-ID rejection;
- full pinned Hugging Face projection parity, uniqueness, and endpoint gates;
- report anchors and no-runner/no-dependency/no-write/no-score boundaries.

## Next Step

Proceed to `memoryarena_projection_integrity_gate`. Materialize all redacted
temporary descriptors outside the AB store, prove canonical output stability
across independent runs, bind a projection digest to the pinned per-config
digests above, and then close or explicitly block the local MemoryArena adapter
lane. Do not begin runner work before that gate closes.
