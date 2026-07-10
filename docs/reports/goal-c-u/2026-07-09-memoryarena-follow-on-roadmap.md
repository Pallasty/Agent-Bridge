# MemoryArena Follow-on Roadmap

Date: 2026-07-09

Source base commit: `50d639da`

Run type: docs-first roadmap and implementation admission plan, no runner

Memory evolution stage:

```yaml
memory_evolution_stage: reflection
experience_candidate_surface: follow_on_roadmap_only
runtime_authority: none
promotion_allowed: false
private_memory_export_allowed: false
third_party_runtime_dependencies: false
no_write_invariant: true
may_write_memory_now: false
may_change_retrieval_order_now: false
```

AB planning anchors:

- Work-memory key:
  `codex-memoryarena-follow-on-roadmap-20260709_active`
- Forum thread: `design#119`, post `2994`
- Parent report:
  `docs/reports/goal-c-u/2026-07-09-memoryarena-task-shape-packet.md`
- Parent durable memory key: `memoryarena_task_shape_packet_20260709`

## Decision

Use a gated MemoryArena sequence instead of treating the existence of public
JSONL as permission to run the official benchmark.

```yaml
selected_now: memoryarena_adapter_contract
next_local_gate: memoryarena_projection_integrity_gate
runner_review_gate: memoryarena_runner_boundary_packet
real_runner_status: explicit_score_objective_required
horizontal_follow_up: ama_bench_interface_shape_packet
fallback_if_memoryarena_blocks: ama_bench_interface_shape_packet
benchmark_performance_claim_allowed: false
dependency_install_allowed_now: false
official_runner_import_allowed_now: false
private_memory_export_allowed: false
writes_ab_store: false
```

The current shape packet already establishes five configs, 701 rows, 10,808
temporary record candidates, 14,952 temporary edge candidates, and 25,760
accepted projection items. The next useful question is whether those candidates
can receive stable, redacted, adapter-family-compatible identities.

## Value And Priority

| Priority | Work packet | Value | Dependency readiness | Risk / cost | Decision |
| --- | --- | --- | --- | --- | --- |
| P0 | `memoryarena_adapter_contract` | Turns observed shape into a reviewable contract with stable temporary record and edge identifiers. This is required by every later integrity or runner decision. | Ready: pinned source, field shapes, counts, and no-write helper already exist. | Low. Standard library, public JSONL, no runner. | Implement now. |
| P1 | `memoryarena_projection_integrity_gate` | Proves full-projection referential integrity, canonical determinism, and parity across all 25,760 candidates before closing the local adapter lane. | Depends on P0 identifier templates and descriptors. | Low to medium. Full temporary materialization, still no runtime write. | Queue immediately after P0. |
| P2 | `ama_bench_interface_shape_packet` | Adds a second long-horizon agent-memory shape and reduces benchmark-design concentration risk. | Source and license anchors exist; interface partition still needs review. | Medium. Trajectory, QA, generation, and judge surfaces must be separated. | Follow P1, or use as fallback if MemoryArena blocks. |
| P2 | `memoryarena_runner_boundary_packet` | Identifies official environment, dependency, API, evaluator, and score-semantics boundaries without crossing them. | Depends on a closed local projection gate so runner work has a stable adapter target. | Medium. External runtime and evaluator semantics. | Review only after P1. |
| HOLD | `memoryarena_real_runner_execution` | Produces benchmark evidence only if scores are an explicit project objective. | Requires a passed runner boundary, execution inputs, credential policy, and score interpretation. | High. Dependencies, environment harness, API/judge cost, and result-governance risk. | Do not start implicitly. |

P1 precedes runner review because a runner cannot repair an unstable local
identity or projection contract. AMA-Bench can follow P1 in parallel with the
runner boundary review because it is a shape-diversification lane, not a
MemoryArena execution dependency.

## Dependency Graph

```text
memoryarena_task_shape_packet (complete)
  -> memoryarena_adapter_contract (P0, now)
     -> memoryarena_projection_integrity_gate (P1)
        -> local MemoryArena adapter closeout
        -> memoryarena_runner_boundary_packet (P2, review only)
           -> explicit score objective + passed boundary
              -> memoryarena_real_runner_execution (HOLD)

memoryarena_projection_integrity_gate
  -> ama_bench_interface_shape_packet (P2 horizontal follow-up)

MemoryArena blocker
  -> ama_bench_interface_shape_packet (fallback)
```

## Packet Gates

### P0: Adapter Contract

Entry gate:

- pinned MemoryArena revision remains
  `da1a37c8b19280e18627ca01cf368195a5e1d92e`;
- five expected configs remain present;
- question/answer and optional background lengths remain aligned;
- no dependency or runner is required.

Required output:

- deterministic temporary IDs for config, task, question, answer-reference,
  non-empty background, and base-person records;
- deterministic IDs for six accepted logical edge kinds;
- redacted representative descriptors, count parity, duplicate-ID checks,
  endpoint checks, and a SQLite no-write sentinel;
- an explicit structural comparison with
  `agent_bridge.realmem_adapter_contract.v0`.

Exit gate:

```yaml
record_count_matches_shape_packet: true
edge_count_matches_shape_packet: true
record_ids_unique: true
edge_ids_unique: true
edge_endpoints_resolve: true
raw_content_redacted: true
no_ab_store_write: true
no_benchmark_performance_claim: true
```

### P1: Projection Integrity Gate

Entry gate: P0 exits with `PASS` on both the offline heterogeneous fixture and
the full pinned public dataset.

Required output:

- materialize all temporary descriptors outside the AB store;
- prove every edge endpoint resolves to exactly one record;
- prove canonical output is identical across two independent runs;
- bind a projection digest to source revision and per-config SHA-256 values;
- close or explicitly block the local MemoryArena adapter lane.

Exit gate: zero duplicates, zero dangling endpoints, stable canonical digest,
shape/adapter count parity, no raw content, and no store deltas.

### P2: Runner Boundary Packet

Entry gate: local MemoryArena adapter lane is closed by P1.

Review only:

- official repository and revision;
- environment harness and browser/tool dependencies;
- API-key, generation, and evaluator requirements;
- score definitions, aggregation, reproducibility, and expected cost;
- synthetic/public input policy versus private AB memory export.

Exit with a bounded `GO`, `NO-GO`, or `OWNER-GATED` decision. This packet does
not install or execute the runner.

### P3: Real Runner Execution

Entry requires all of:

- an explicit request for benchmark scores;
- a passed P2 boundary;
- approved public or synthetic evaluation inputs;
- resolved dependency, credential, cost, and result-retention policy;
- pre-registered score interpretation and rollback/cleanup steps.

Missing any item keeps this lane on `HOLD`.

## In-turn Implementation Scope

This turn may implement only `memoryarena_adapter_contract` after this roadmap
is committed. The implementation may add a standard-library helper, offline
verifier, and report. It may read the pinned public JSONL revision and an
optional SQLite store only for before/after row counts.

The implementation must not:

- import, clone, vendor, or execute the MemoryArena runner;
- install Python, Rust, npm, browser, Docker, Hugging Face, or system
  dependencies;
- call an LLM or API-key-backed generator or judge;
- export private AB memory;
- write records, edges, or semantic events into the AB store;
- change MCP tools, database schema, retrieval, bootstrap, consolidation,
  trigger recall, workflow feedback, or daemon configuration;
- claim benchmark score, accuracy, or performance.

## Replan Triggers

Stop P0 and replan if:

- the pinned revision or expected config set changes;
- shape counts diverge without an explained source change;
- source IDs cannot produce unique stable task identities;
- heterogeneous answer or base-person values leak into packet output;
- any AB store delta is observed.

After P0, choose P1 unless one of those triggers fires. Choose AMA-Bench early
only when MemoryArena blocks or when a separate owner decision prioritizes
portfolio breadth over closing the MemoryArena local adapter lane.

## Verification

```bash
bash -n scripts/verify-memoryarena-follow-on-roadmap.sh
scripts/verify-memoryarena-follow-on-roadmap.sh
git diff --check
```

The verifier asserts the priority order, dependencies, packet entry/exit gates,
implementation scope, and no-runner/no-dependency/no-write/no-score boundary.

## Next Step

Commit this roadmap, then implement `memoryarena_adapter_contract` against its
P0 entry and exit gates.
