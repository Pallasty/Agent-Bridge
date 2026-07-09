# RealMem Resolved Projection Gate

Date: 2026-07-09

Source base commit: `a414a83a`

Run type: local resolved projection gate, no RealMem runner

Memory evolution stage:

```yaml
memory_evolution_stage: reflection
experience_candidate_surface: resolved_projection_gate_only
runtime_authority: none
promotion_allowed: false
private_memory_export_allowed: false
third_party_runtime_dependencies: false
no_write_invariant: true
may_write_memory_now: false
may_change_retrieval_order_now: false
```

AB planning anchors:

- Durable memory key: `realmem_resolved_projection_gate_20260709`
- Work-memory key: `codex-realmem-resolved-projection-gate-20260709_active`
- Forum thread: `design#119`, post `2987`
- Parent report:
  `docs/reports/goal-c-u/2026-07-09-realmem-reference-resolver-packet.md`
- Parent durable memory key: `realmem_reference_resolver_packet_20260709`

External anchors:

- Repository: https://github.com/AvatarMemory/RealMemBench
- Observed repository HEAD: `67afd0891d603adcc4458ff0449df306ef296b7a`
- Observed license: `Apache-2.0`
- Pinned sample:
  `https://raw.githubusercontent.com/AvatarMemory/RealMemBench/67afd0891d603adcc4458ff0449df306ef296b7a/dataset/Lin_Wanyu_dialogues_256k.json`

## Verdict

`realmem_resolved_projection_gate` is implemented as a standard-library helper
and offline verifier.

The gate combines:

- `agent_bridge.realmem_dialogue_shape_packet.v0`;
- `agent_bridge.realmem_adapter_contract.v0`;
- `agent_bridge.realmem_reference_resolver.v0`.

On the pinned `Lin_Wanyu` sample, the gate accepts the full temporary projection
candidate set: 2060 records and 3060 resolved temporary edges. The only
remaining unresolved references are 7 negative `source_turn` values, which are
not edge candidates and are explicitly kept out of the accepted projection.

This is not a RealMem benchmark score.

## Landed Files

```text
scripts/realmem-resolved-projection-gate.py
scripts/verify-realmem-resolved-projection-gate.sh
docs/reports/goal-c-u/2026-07-09-realmem-resolved-projection-gate.md
```

## Gate Schema

```yaml
schema: agent_bridge.realmem_resolved_projection_gate.v0
shape_schema: agent_bridge.realmem_dialogue_shape_packet.v0
adapter_schema: agent_bridge.realmem_adapter_contract.v0
resolver_schema: agent_bridge.realmem_reference_resolver.v0
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

Default source safety:

- `http://` URLs are refused by the shared shape loader;
- non-pinned RealMem raw URLs are refused unless `--allow-other-url` is passed
  for review-only overrides;
- no RealMem package or official eval module is imported;
- no dependency is installed;
- raw dialogue and memory content values are not emitted.

## Pinned Sample Result

Command shape:

```bash
scripts/realmem-resolved-projection-gate.py --store-db "$tmpdir/state.db" --output "$tmpdir/gate.json"
```

Observed result:

```yaml
verdict: PASS
source_sha256: a7a751066c48e829b3012a94f2b365febd0e6fb6db454a6d5f4ec01f9c55008a
projected_record_count: 2060
adapter_accepted_edge_count: 2703
resolver_added_memory_used_edges: 327
resolver_added_fallback_source_turn_edges: 30
final_accepted_edge_count: 3060
adapter_edge_candidate_count: 3060
resolved_reference_count: 763
residual_unresolved_count: 7
residual_unresolved_counts:
  memory_used_ambiguous: 0
  memory_used_bad_shape: 0
  memory_used_missing: 0
  source_turn_negative: 7
  source_turn_out_of_range: 0
accepted_projection_item_count: 5120
```

Acceptance gates:

```yaml
source_pinned: true
shape_schema_matches: true
adapter_schema_matches: true
resolver_schema_matches: true
adapter_verdict_pass: true
resolver_verdict_pass: true
record_count_matches_adapter: true
final_accepted_edges_match_adapter_candidates: true
memory_used_fully_resolved: true
source_turn_indexing_fully_resolved: true
residual_unresolved_only_negative_source_turn: true
raw_content_redacted: true
no_ab_store_write: true
no_benchmark_performance_claim: true
no_write_invariant:
  checked: true
  passed: true
  memory_rows_delta: 0
  memory_edges_delta: 0
  semantic_events_delta: 0
```

## Gate Meaning

The gate means the pinned sample can now be projected into a complete local
temporary graph for all accepted edge candidates:

```yaml
temporary_records: 2060
temporary_edges: 3060
accepted_projection_items: 5120
```

It does not mean AB has answered RealMem tasks. The gate only proves local
source-shape, projection, and reference-resolution consistency.

The residual 7 negative `source_turn` values remain visible as data-quality
gaps. They do not block the local projection gate because they were never
candidate edges in the shape packet and are not silently converted into graph
links.

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
python3 -m py_compile scripts/realmem-resolved-projection-gate.py scripts/realmem-reference-resolver.py scripts/realmem-adapter-contract.py scripts/realmem-dialogue-shape-inspector.py
bash -n scripts/verify-realmem-resolved-projection-gate.sh
scripts/verify-realmem-resolved-projection-gate.sh
git diff --check
```

The verifier uses an offline RealMem-shaped fixture and sentinel SQLite store to
assert:

- output schema, source pin, and no-runner/no-dependency/no-API flags;
- final accepted edge count equals adapter edge candidate count;
- `memory_used` and source-turn indexing ambiguities are resolved;
- residual unresolved references are only negative source-turn gaps;
- no-write deltas;
- raw fixture content values are absent from output;
- unpinned `main` raw URLs are refused.

## Next Step

Proceed with `realmem_real_runner_boundary_packet` only if benchmark scores are
now explicitly desired. Otherwise, close the RealMem local adapter chain here
and return to survey-level comparison with MemoryArena or AMA-Bench.
