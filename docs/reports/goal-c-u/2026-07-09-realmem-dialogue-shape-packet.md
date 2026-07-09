# RealMem Dialogue Shape Packet

Date: 2026-07-09

Source base commit: `ec7e2ab6`

Run type: standard-library shape inspection, no RealMem runner

Memory evolution stage:

```yaml
memory_evolution_stage: reflection
experience_candidate_surface: shape_only
runtime_authority: none
promotion_allowed: false
private_memory_export_allowed: false
third_party_runtime_dependencies: false
no_write_invariant: true
may_write_memory_now: false
may_change_retrieval_order_now: false
```

AB planning anchors:

- Durable memory key: `realmem_dialogue_shape_packet_20260709`
- Work-memory key: `codex-realmem-dialogue-shape-20260709_active`
- Forum thread: `design#119`, post `2981`
- Parent report:
  `docs/reports/goal-c-u/2026-07-09-memory-survey-next-benchmark-retriage.md`
- Parent durable memory key: `memory_survey_next_benchmark_retriage_20260709`

External anchors:

- Repository: https://github.com/AvatarMemory/RealMemBench
- RealMem paper: https://arxiv.org/abs/2601.06966
- Observed repository HEAD: `67afd0891d603adcc4458ff0449df306ef296b7a`
- Observed default branch: `main`
- Observed license: `Apache-2.0`
- Pinned sample:
  `https://raw.githubusercontent.com/AvatarMemory/RealMemBench/67afd0891d603adcc4458ff0449df306ef296b7a/dataset/Lin_Wanyu_dialogues_256k.json`

## Verdict

`realmem_dialogue_shape_packet` is implemented as a local shape inspector and
offline verifier.

This packet proves that AB can inspect a commit-pinned RealMem dialogue JSON and
produce a redacted projection contract without running RealMem evaluation,
installing RealMem dependencies, calling an LLM, exporting private AB memory, or
writing the AB store.

This is not a RealMem benchmark score.

## Landed Files

```text
scripts/realmem-dialogue-shape-inspector.py
scripts/verify-realmem-dialogue-shape-packet.sh
docs/reports/goal-c-u/2026-07-09-realmem-dialogue-shape-packet.md
```

## Source Validation

Bounded source checks on 2026-07-09:

| Check | Result |
| --- | --- |
| Repository | `AvatarMemory/RealMemBench` |
| Repository HEAD | `67afd0891d603adcc4458ff0449df306ef296b7a` |
| Default branch | `main` |
| API `pushed_at` | `2026-04-07T04:42:17Z` |
| API license | `Apache-2.0` |
| Tree status | not truncated |
| Tree path count | 82 |
| Dataset JSON count | 13 |
| Required source files observed | `LICENSE`, `README.md`, `requirements.txt`, `dataset/`, `eval/` |

The upstream README describes RealMem as a multi-session long-term-memory
dialogue benchmark and documents `_metadata`, `dialogues`, `dialogue_turns`,
`extracted_memory`, `memory_used`, and `memory_session_uuids` fields. It also
describes dependency setup, API-key configuration, generation, and evaluation
commands. Those runtime paths are outside this packet.

## Inspector Contract

`scripts/realmem-dialogue-shape-inspector.py` is standard-library-only.

It accepts a local JSON file or commit-pinned RealMem raw URL. By default it
loads:

```text
https://raw.githubusercontent.com/AvatarMemory/RealMemBench/67afd0891d603adcc4458ff0449df306ef296b7a/dataset/Lin_Wanyu_dialogues_256k.json
```

Default URL safety:

- `http://` URLs are refused;
- non-pinned RealMem URLs are refused unless `--allow-other-url` is explicitly
  passed for review-only overrides;
- no RealMem package or official eval module is imported;
- no dependency is installed.

The output schema is:

```yaml
schema: agent_bridge.realmem_dialogue_shape_packet.v0
source_repo: https://github.com/AvatarMemory/RealMemBench
source_head: 67afd0891d603adcc4458ff0449df306ef296b7a
official_runner_import_allowed: false
realmem_runner_allowed_now: false
third_party_runtime_dependencies: false
api_key_required: false
private_memory_export_allowed: false
writes_ab_store: false
benchmark_performance_claim: false
raw_content_in_output: false
```

When `--store-db` is provided, the helper reads row counts for `memories`,
`memory_edges`, and `semantic_events` before and after inspection. It does not
write those tables.

## Pinned Sample Result

Command shape:

```bash
scripts/realmem-dialogue-shape-inspector.py --store-db "$tmpdir/state.db" --output "$tmpdir/shape.json"
```

Observed output summary on the pinned `Lin_Wanyu` sample:

```yaml
person_name: Lin_Wanyu
total_sessions: 207
total_tokens: 227417
source_sha256: a7a751066c48e829b3012a94f2b365febd0e6fb6db454a6d5f4ec01f9c55008a
session_count: 207
turn_count: 1284
query_turn_count: 126
non_bool_is_query_count: 1
extracted_memory_count: 443
empty_extracted_memory_content_count: 0
source_turn_reference_count: 436
memory_used_turn_count: 128
memory_session_uuid_turn_count: 128
memory_used_reference_count: 327
memory_session_uuid_reference_count: 238
temporary_record_count: 2060
temporary_edge_count: 3060
speaker_counts:
  Assistant: 642
  User: 642
is_query_shapes:
  bool: 1283
  null: 1
memory_type_counts:
  Dynamic: 355
  Schedule: 7
  Static: 81
extracted_memory_content_shapes:
  object: 1
  string: 442
session_type_counts:
  multi_session: 61
  single_session: 65
category_counts:
  Dynamic Incremental: 97
  Dynamic Updating: 17
  Implicit Preference: 9
  Temporal-reasoning: 3
edge_type_counts:
  chronologically_before: 206
  contains_extracted_memory: 443
  contains_turn: 1284
  derived_from_source_turn: 436
  query_turn_record: 126
  uses_memory: 327
  uses_memory_session: 238
no_write_invariant:
  checked: true
  passed: true
  memory_rows_delta: 0
  memory_edges_delta: 0
  semantic_events_delta: 0
```

## Shape Caveats

The pinned sample should not be treated as a perfectly normalized schema.

Observed caveats:

- `is_query` has 1 `null` value, so future adapters must not assume every turn
  has a boolean query marker.
- `extracted_memory.content` has 1 object and 442 strings, so future adapters
  must track content shape before treating memory content as plain text.
- `source_turn_reference_count` is 436 while extracted-memory count is 443, so
  some extracted memories do not map to a non-negative source turn.
- `session_type_counts` and `category_counts` are lower than turn count because
  those fields are sparse metadata.

These caveats strengthen the case for a shape packet before any retrieval or
evaluation runner work.

## AB Projection Contract

The helper only creates temporary in-memory record and edge counts. It does not
write AB memory.

Temporary record kinds:

```text
benchmark_synthetic_persona_session
benchmark_synthetic_dialogue_turn
benchmark_synthetic_extracted_memory
benchmark_synthetic_query_turn
```

Temporary edge kinds:

```text
chronologically_before
contains_turn
contains_extracted_memory
derived_from_source_turn
query_turn_record
uses_memory
uses_memory_session
```

Adapter interpretation:

- sessions can become temporary chronological `MemoryRecord` candidates;
- dialogue turns can become temporary event records;
- extracted memories can become temporary synthetic memory candidates;
- query turns can become temporary retrieval/usage probes;
- `memory_used` and `memory_session_uuids` can become query-evidence links;
- all projection keys and edges stay local to the shape packet.

## Boundary

This packet did not:

- clone, vendor, import, or execute RealMem official code;
- run RealMem generation, retrieval, evaluation, or metric scripts;
- install Python, Rust, npm, Docker, or system dependencies;
- call an LLM or API-key-backed evaluator;
- export private AB memory data;
- write to the AB memory store;
- add a DB schema, MCP tool, feature flag, or runtime process;
- change retrieval, bootstrap, consolidation, trigger-recall, workflow-feedback,
  forum status, or daemon configuration;
- claim RealMem score, benchmark accuracy, or benchmark performance.

## Verification

Commands:

```bash
python3 -m py_compile scripts/realmem-dialogue-shape-inspector.py
bash -n scripts/verify-realmem-dialogue-shape-packet.sh
scripts/verify-realmem-dialogue-shape-packet.sh
git diff --check
```

The verifier uses an offline RealMem-shaped fixture and a sentinel SQLite store
to assert:

- output schema and source pin;
- no official runner import, no dependency, no API key, no private memory
  export, no AB store write, and no benchmark claim;
- temporary record and edge counts;
- content values are not emitted in the redacted output;
- unpinned `main` raw URLs are refused.

## Next Step

Proceed with `realmem_adapter_contract_packet`: use the shape inspector output
to define exact AB projection rows and local acceptance gates. Do not run
RealMem evaluation or install RealMem dependencies before that packet exists.
