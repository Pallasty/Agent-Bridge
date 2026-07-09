# RealMem Adapter Contract Packet

Date: 2026-07-09

Source base commit: `26527973`

Run type: no-write adapter contract implementation

Memory evolution stage:

```yaml
memory_evolution_stage: reflection
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

- Durable memory key: `realmem_adapter_contract_packet_20260709`
- Work-memory key: `codex-realmem-adapter-contract-20260709_active`
- Forum thread: `design#119`, post `2983`
- Parent report:
  `docs/reports/goal-c-u/2026-07-09-realmem-dialogue-shape-packet.md`
- Parent durable memory key: `realmem_dialogue_shape_packet_20260709`

External anchors:

- Repository: https://github.com/AvatarMemory/RealMemBench
- Observed repository HEAD: `67afd0891d603adcc4458ff0449df306ef296b7a`
- Observed license: `Apache-2.0`
- Pinned sample:
  `https://raw.githubusercontent.com/AvatarMemory/RealMemBench/67afd0891d603adcc4458ff0449df306ef296b7a/dataset/Lin_Wanyu_dialogues_256k.json`

## Verdict

`realmem_adapter_contract_packet` is implemented as a standard-library helper
and offline verifier.

The helper converts a RealMem dialogue shape into a redacted AB adapter contract
for temporary `MemoryRecord` and `MemoryEdge` projections. It preserves the
shape packet's no-write boundary and adds a stricter gate: RealMem
`memory_used` content references are not treated as precise graph edges until a
separate resolver can map them to exact extracted-memory IDs.

This is not a RealMem benchmark score.

## Landed Files

```text
scripts/realmem-adapter-contract.py
scripts/verify-realmem-adapter-contract.sh
docs/reports/goal-c-u/2026-07-09-realmem-adapter-contract-packet.md
```

## Contract Schema

```yaml
schema: agent_bridge.realmem_adapter_contract.v0
shape_schema: agent_bridge.realmem_dialogue_shape_packet.v0
source_head: 67afd0891d603adcc4458ff0449df306ef296b7a
official_runner_import_allowed: false
realmem_runner_allowed_now: false
third_party_runtime_dependencies: false
api_key_required: false
private_memory_export_allowed: false
writes_ab_store: false
benchmark_performance_claim: false
raw_content_in_output: false
scope: benchmark:realmem
```

Default source safety:

- `http://` URLs are refused by the shape loader;
- non-pinned RealMem raw URLs are refused unless `--allow-other-url` is passed
  for review-only overrides;
- no RealMem package or official eval module is imported;
- no dependency is installed;
- raw dialogue and memory content values are not emitted.

## Projection Contract

Temporary `MemoryRecord` kinds:

```yaml
benchmark_synthetic_realmem_session: 207
benchmark_synthetic_realmem_turn: 1284
benchmark_synthetic_realmem_extracted_memory: 443
benchmark_synthetic_realmem_query_turn: 126
projected_record_count: 2060
```

Accepted temporary edge kinds:

```yaml
chronologically_before: 206
contains_turn: 1284
contains_extracted_memory: 443
derived_from_source_turn: 406
query_turn_record: 126
uses_memory_session: 238
accepted_memory_edge_count: 2703
```

Unresolved reference candidates:

```yaml
memory_used_content_reference: 327
source_turn_indexing_reference: 30
unresolved_reference_count: 357
edge_candidate_count: 3060
```

Interpretation:

- session, turn, extracted-memory, and query-turn records have stable synthetic
  keys under `benchmark:realmem`;
- chronology, containment, source-turn, query-record, and session-UUID
  references are safe as temporary edge candidates;
- `memory_used` content references are evidence that a turn used memory, but
  they are not exact extracted-memory IDs;
- non-negative `source_turn` values that do not resolve under zero-based
  indexing are preserved as unresolved indexing references, not forced into
  edges.

## Pinned Sample Result

Command shape:

```bash
scripts/realmem-adapter-contract.py --store-db "$tmpdir/state.db" --output "$tmpdir/contract.json"
```

Observed result on the pinned `Lin_Wanyu` sample:

```yaml
verdict: PASS
source_sha256: a7a751066c48e829b3012a94f2b365febd0e6fb6db454a6d5f4ec01f9c55008a
record_count_matches_shape_packet: true
edge_candidate_count_matches_shape_packet: true
accepted_edges_exclude_memory_used_content_refs: true
raw_content_redacted: true
no_ab_store_write: true
no_benchmark_performance_claim: true
memory_rows_delta: 0
memory_edges_delta: 0
semantic_events_delta: 0
```

Data-quality flags:

```yaml
non_bool_is_query_count: 1
non_string_memory_content_count: 1
source_turn_unresolved_count: 37
source_turn_negative_count: 7
source_turn_indexing_reference_count: 30
memory_used_content_reference_count: 327
memory_used_requires_resolver: true
memory_content_shape_counts:
  object: 1
  string: 442
```

## Why `memory_used` Stays Unresolved

RealMem `memory_used` entries contain content/session metadata, not the stable
`extracted_memory.index` field. Mapping them directly to extracted-memory
records would require a resolver policy, such as exact content matching,
session-scoped matching, canonical JSON normalization, or tolerance for
duplicate memory text.

This packet deliberately refuses to guess that mapping. It keeps those 327
references as unresolved evidence and blocks real benchmark evaluation until a
resolver packet exists.

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
python3 -m py_compile scripts/realmem-adapter-contract.py scripts/realmem-dialogue-shape-inspector.py
bash -n scripts/verify-realmem-adapter-contract.sh
scripts/verify-realmem-adapter-contract.sh
git diff --check
```

The verifier uses an offline RealMem-shaped fixture and sentinel SQLite store to
assert:

- output schema, source pin, and no-runner/no-dependency/no-API flags;
- exact projected record counts;
- accepted edge counts;
- unresolved `memory_used` and `source_turn` reference handling;
- no-write deltas;
- raw fixture content values are absent from output;
- unpinned `main` raw URLs are refused.

## Next Step

Proceed with `realmem_reference_resolver_packet`: define local-only resolver
rules for `memory_used` content references and source-turn indexing ambiguity.
Do not run RealMem evaluation or install RealMem dependencies before that
resolver packet exists.
