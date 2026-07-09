# RealMem Reference Resolver Packet

Date: 2026-07-09

Source base commit: `4b69606e`

Run type: no-write local reference resolver

Memory evolution stage:

```yaml
memory_evolution_stage: reflection
experience_candidate_surface: resolver_contract_only
runtime_authority: none
promotion_allowed: false
private_memory_export_allowed: false
third_party_runtime_dependencies: false
no_write_invariant: true
may_write_memory_now: false
may_change_retrieval_order_now: false
```

AB planning anchors:

- Durable memory key: `realmem_reference_resolver_packet_20260709`
- Work-memory key: `codex-realmem-reference-resolver-20260709_active`
- Forum thread: `design#119`, post `2985`
- Parent report:
  `docs/reports/goal-c-u/2026-07-09-realmem-adapter-contract-packet.md`
- Parent durable memory key: `realmem_adapter_contract_packet_20260709`

External anchors:

- Repository: https://github.com/AvatarMemory/RealMemBench
- Observed repository HEAD: `67afd0891d603adcc4458ff0449df306ef296b7a`
- Observed license: `Apache-2.0`
- Pinned sample:
  `https://raw.githubusercontent.com/AvatarMemory/RealMemBench/67afd0891d603adcc4458ff0449df306ef296b7a/dataset/Lin_Wanyu_dialogues_256k.json`

## Verdict

`realmem_reference_resolver_packet` is implemented as a standard-library helper
and offline verifier.

The resolver defines two deterministic local rules:

```yaml
memory_used_rule: "session_uuid + exact string content -> exactly one extracted_memory"
source_turn_rule: "zero_based first; one_based fallback only when zero_based is out of range and 1 <= source_turn <= turn_count; negative remains unresolved"
```

On the pinned `Lin_Wanyu` sample, the resolver converts all 327
`memory_used_content_reference` items and all 30
`source_turn_indexing_reference` items from the adapter contract into resolved
local references. The only remaining unresolved references are 7 negative
`source_turn` values.

This is not a RealMem benchmark score.

## Landed Files

```text
scripts/realmem-reference-resolver.py
scripts/verify-realmem-reference-resolver.sh
docs/reports/goal-c-u/2026-07-09-realmem-reference-resolver-packet.md
```

## Resolver Schema

```yaml
schema: agent_bridge.realmem_reference_resolver.v0
adapter_schema: agent_bridge.realmem_adapter_contract.v0
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
scripts/realmem-reference-resolver.py --store-db "$tmpdir/state.db" --output "$tmpdir/resolver.json"
```

Observed result:

```yaml
verdict: PASS
source_sha256: a7a751066c48e829b3012a94f2b365febd0e6fb6db454a6d5f4ec01f9c55008a
resolved_reference_count: 763
unresolved_reference_count: 7
resolved_memory_used_edge_count: 327
resolved_source_turn_edge_count: 406
fallback_source_turn_edge_count: 30
resolution_counts:
  memory_used_exact_session_content: 327
  source_turn_one_based_fallback: 30
  source_turn_zero_based: 406
unresolved_counts:
  memory_used_ambiguous: 0
  memory_used_bad_shape: 0
  memory_used_missing: 0
  source_turn_negative: 7
  source_turn_out_of_range: 0
acceptance_gates:
  source_pinned: true
  adapter_schema_matches: true
  memory_used_resolution_count_matches_adapter: true
  source_turn_fallback_count_matches_adapter: true
  source_turn_negative_count_matches_adapter: true
  resolved_plus_unresolved_matches_adapter: true
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

## Resolver Rules

### `memory_used`

Input:

```yaml
turn.memory_used[].session_uuid: required string
turn.memory_used[].content: required string
```

Resolution:

1. Collect extracted memories indexed by `(session_uuid, content)` when
   `extracted_memory.content` is a string.
2. A `memory_used` reference resolves only when that pair has exactly one
   extracted-memory match.
3. Missing, ambiguous, or non-string references remain unresolved and block any
   future real-eval lane.

Pinned sample result: `327/327` `memory_used` references resolve uniquely.

### `source_turn`

Resolution:

1. Prefer zero-based indexing when `0 <= source_turn < turn_count`.
2. Use one-based fallback only when zero-based is out of range and
   `1 <= source_turn <= turn_count`.
3. Keep negative values unresolved.

Pinned sample result: `406` zero-based references resolve, `30` one-based
fallback references resolve with `review_recommended=true`, and `7` negative
references remain unresolved.

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
python3 -m py_compile scripts/realmem-reference-resolver.py scripts/realmem-adapter-contract.py scripts/realmem-dialogue-shape-inspector.py
bash -n scripts/verify-realmem-reference-resolver.sh
scripts/verify-realmem-reference-resolver.sh
git diff --check
```

The verifier uses an offline RealMem-shaped fixture and sentinel SQLite store to
assert:

- output schema, source pin, and no-runner/no-dependency/no-API flags;
- `memory_used` exact session/content resolution;
- source-turn zero-based and one-based fallback behavior;
- negative source-turn references remain unresolved;
- no-write deltas;
- raw fixture content values are absent from output;
- unpinned `main` raw URLs are refused.

## Next Step

Proceed with `realmem_resolved_projection_gate`: combine the adapter contract
and resolver output into a local acceptance gate for the pinned sample. Do not
run RealMem evaluation or install RealMem dependencies before that gate exists.
