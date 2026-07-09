# StructMemEval Fit Packet

Date: 2026-07-09

Source base commit: `a76739d2`

Run type: docs-only external benchmark fit packet

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

- Durable memory key: `structmemeval_fit_packet_20260709`
- Forum thread: `design#119`, post `2955`
- Parent report:
  `docs/reports/goal-c-u/2026-07-09-memory-survey-benchmark-triage.md`
- Prior report convention:
  `docs/reports/goal-c-u/2026-07-09-belief-clarity-diagnostic-packet.md`

External anchors:

- Paper: https://arxiv.org/abs/2602.11243
- Paper HTML v2: https://arxiv.org/html/2602.11243v2
- Repository: https://github.com/yandex-research/StructMemEval
- Observed repository HEAD: `64d2c9b242deb394e3ef94a318868a55261e141b`

## Verdict

StructMemEval remains the best first external benchmark fit for AB's structured
memory lane, but only as a no-write adapter contract for now.

The current repository exposes synthetic benchmark data with a uniform
`case_id / sessions[] / queries[]` shape across accounting, tree, state, and
recommendation tasks. That shape is compatible with an AB projection that
creates temporary `MemoryRecord` and `MemoryEdge` views without exporting or
mutating the real AB memory store.

Do not vendor StructMemEval, install its official dependencies, run API-key
evaluations, or add an MCP runner in this slice.

## Boundary

This packet:

- does not clone or vendor external code into this repository;
- does not import official benchmark modules;
- does not install Python dependencies;
- does not run API-key-backed evaluations;
- does not export private AB memories;
- does not write to the AB memory store;
- does not add a DB schema, MCP tool, or runtime feature flag;
- does not change retrieval, bootstrap, consolidation, trigger-recall, or
  workflow-feedback behavior.

## External Validation

Current source state verified on 2026-07-09:

| Check | Result |
| --- | --- |
| arXiv title | `Evaluating Memory Structure in LLM Agents` |
| arXiv version | `2602.11243v2`, dated 2026-05-22 |
| Repository default branch | `main` |
| Repository HEAD | `64d2c9b242deb394e3ef94a318868a55261e141b` |
| Repository license | Apache-2.0 |
| Repository update observed by API | `pushed_at=2026-06-29T15:08:26Z` |
| Raw benchmark families | `accounting`, `tree_based`, `state_machine_location`, `recommendations` |

Inspection notes:

- A full shallow clone to `/tmp` disconnected during fetch, so this pass used
  GitHub API and raw-file reads for bounded inspection.
- The official README's runner path requires API keys and external memory
  systems/dependencies such as `mem0`, Qdrant, mem-agent, and EMem.
- `requirements.txt` includes heavyweight benchmark/eval dependencies. Those
  are not acceptable as AB runtime dependencies for this slice.

Representative verification commands:

```bash
git ls-remote https://github.com/yandex-research/StructMemEval.git HEAD
curl -L --fail --silent https://api.github.com/repos/yandex-research/StructMemEval
curl -L --fail --silent 'https://api.github.com/repos/yandex-research/StructMemEval/git/trees/main?recursive=1'
curl -L --fail --silent https://raw.githubusercontent.com/yandex-research/StructMemEval/main/benchmark/data/accounting/debt_tracker_10_1.json
```

## Data Shape Findings

Raw benchmark data is organized as JSON case files plus `dataset.yaml` and
prompt files. Bounded file-tree inspection found this benchmark/data breakdown:

| Family | Files under `benchmark/data/<family>` | Sample path inspected | Shape |
| --- | ---: | --- | --- |
| `accounting` | 27 | `accounting/debt_tracker_10_1.json` | One session, ledger-like user events, one settlement query |
| `tree_based` | 30 | `tree_based/big_bench/graph_0_trimmed_10_with_path_1.json` | One session, graph relation events, many relation/path queries |
| `state_machine_location` | 66 | `state_machine_location/big_bench/static_001.json` | Several sessions, location/state facts, one or more recall/state queries |
| `recommendations` | 93 | `recommendations/benchmark_data/books_data_275.json` | Many sessions, preference/fact metadata, many aggregation queries |

Observed common top-level shape:

```json
{
  "case_id": "string",
  "sessions": [
    {
      "session_id": "string",
      "topic": "string",
      "messages": [
        {
          "role": "user|assistant",
          "content": "string"
        }
      ]
    }
  ],
  "queries": [
    {
      "query_id": "optional string",
      "question": "string",
      "reference_answer": "string|object|array"
    }
  ]
}
```

Additional fields appear in some recommendation sessions:

```json
{
  "contains_fact": true,
  "fact_id": "fantasy_preference",
  "fact_quote": "..."
}
```

The adapter must therefore treat `case_id`, `sessions`, and `queries` as the
portable core and keep family-specific metadata optional.

## AB Fit

StructMemEval targets memory organization, not just factual recall. This maps
well to existing AB surfaces:

- `MemoryRecord`: temporary synthetic event/fact records can represent session
  turns and derived structured notes.
- `MemoryEdge`: temporary synthetic graph edges can represent tree/path
  structure, derived-from links, and query-to-evidence relations.
- `memory_related_keys_*`: future dry-run packets can evaluate whether explicit
  links reduce orphaned evidence without writing edges.
- `memory_consolidation_queue.v1`: future shadow packets can evaluate whether
  duplicate/stale/too-large signals remain separated from task answer quality.
- `outcome_gated_consolidation_*`: future write-capable experiments must pass
  the existing staged gates, but this fit packet does not enter that lane.

Local source anchors:

- `crates/store/src/lib.rs:259` defines `MemoryRecord`.
- `crates/store/src/lib.rs:307` defines `MemoryEdge`.
- `crates/bridge/src/mcp_tools.rs:29252` defines
  `memory_consolidation_queue_from_records`.

## Adapter Contract

This is a report-local contract, not a persisted schema.

```json
{
  "schema": "agent_bridge.structmemeval_fit_packet.v0",
  "contract_id": "structmemeval_no_write_projection_20260709",
  "source_repo": "https://github.com/yandex-research/StructMemEval",
  "source_head": "64d2c9b242deb394e3ef94a318868a55261e141b",
  "allowed_input": "synthetic StructMemEval JSON cases only",
  "private_memory_export_allowed": false,
  "third_party_runtime_dependencies": false,
  "official_runner_import_allowed": false,
  "api_key_required": false,
  "no_write_invariant": true,
  "promotion_allowed": false,
  "projection": {
    "case_id": "case.case_id",
    "sessions": "case.sessions[]",
    "turns": "session.messages[]",
    "queries": "case.queries[]",
    "reference_answers": "query.reference_answer"
  },
  "temporary_memory_record": {
    "key": "structmemeval:{family}:{case_id}:session:{session_id}:turn:{turn_index}",
    "kind": "benchmark_synthetic_event",
    "content": "{role}: {content}",
    "tags": [
      "structmemeval",
      "synthetic",
      "no_write",
      "family:{family}"
    ],
    "scope": "benchmark:structmemeval",
    "status": "active"
  },
  "temporary_edge": {
    "from_key": "query_or_derived_record",
    "to_key": "supporting_event_or_fact",
    "edge_type": "derived_from|relates|supports_answer",
    "weight": 1.0
  }
}
```

Required invariant for any future implementation:

```yaml
no_write_invariant:
  ab_store_before_hash: required
  ab_store_after_hash: required
  memory_rows_delta: 0
  memory_edges_delta: 0
  semantic_events_delta: 0
  private_memory_export_allowed: false
  third_party_runtime_dependencies: false
```

## Task Family Mapping

| Family | Memory structure tested | AB projection | First useful metric | Fit |
| --- | --- | --- | --- | --- |
| `tree_based` | Graph/path organization | Temporary relation edges plus query-to-path evidence | path/relation answer accuracy and edge coverage | **P0** |
| `state_machine_location` | State tracking over sessions | Versioned temporary fact records; optional supersedes-style derived facts | final-state accuracy and stale-state avoidance | **P0** |
| `accounting` | Ledger aggregation | Temporary transaction facts and derived settlement records | numeric settlement correctness and distractor resistance | **P1** |
| `recommendations` | Preference/fact aggregation | Temporary preference facts, fact ids, query evidence links | required-fact recall and aggregation correctness | **P1/P2** |

Recommended first evaluation subset:

1. `tree_based/big_bench/graph_0_trimmed_10_with_path_1.json`
2. `state_machine_location/big_bench/static_001.json`
3. `accounting/debt_tracker_10_1.json`

Reason: these samples cover graph, state, and ledger behavior with small enough
surface area to validate the adapter contract without official dependencies.

## Metric Pre-Registration

No future run should claim benchmark success without recording these metrics:

| Metric | Definition | Required for |
| --- | --- | --- |
| `input_case_count` | Number of StructMemEval cases loaded | all runs |
| `session_turn_coverage` | Loaded turns divided by source turns | all runs |
| `query_count` | Number of queries evaluated | all runs |
| `reference_answer_shape` | string/object/array distribution | all runs |
| `retrieval_hit_rate` | Query evidence retrieved before answer generation | retrieval smoke |
| `structure_edge_coverage` | Expected/derived relation edges represented in the temporary projection | tree/state tasks |
| `answer_accuracy` | Exact/normalized or judge-scored correctness against reference answer | full eval only |
| `distractor_resistance` | Correct answer despite irrelevant session turns | accounting/state/recommendations |
| `token_cost` | Prompt/input tokens by case and query | any LLM-backed run |
| `latency_ms` | Per case/query wall-clock time | any runner |
| `no_write_invariant` | AB store row/edge/event deltas remain zero | all runs |

Accuracy scoring must be family-specific:

- tree/state: prefer deterministic normalized checks when possible;
- accounting: require numeric normalization and tolerance policy before any LLM
  judge;
- recommendations: use `required_facts` when present before relying on a judge;
- LLM-as-judge can be added later, but must be separately labeled.

## Belief Clarity Check

```yaml
belief_clarity_check:
  schema: agent_bridge.memory_belief_clarity_diagnostic.v0
  anchor_question: "Based on current memory, what is current task progress and what information is still needed?"
  progress_known:
    - "StructMemEval is current enough to inspect, with v2 paper and repo HEAD 64d2c9b."
    - "License is Apache-2.0 according to GitHub API and LICENSE source."
    - "Raw JSON cases have a common case_id/sessions/queries shape."
    - "Official runner dependencies and API-key requirements make direct adoption inappropriate for AB."
  information_missing:
    - "No local adapter implementation exists."
    - "No deterministic answer normalizers have been defined for accounting/tree/state/recommendation families."
    - "No isolated temp-store no-write assertion exists yet."
    - "No owner approval exists for adding a runner or vendoring fixtures."
  blockers:
    - "Do not run official benchmark code inside AB."
    - "Do not export private AB memory for benchmark evaluation."
    - "Do not claim benchmark accuracy until a separate implementation packet runs a bounded subset."
  uncertainty_markers:
    - "Full shallow clone disconnected; bounded API/raw-file inspection was used instead."
    - "Repository is marked work in progress."
    - "Official benchmark uses LLM/API-backed judging paths that were not executed."
  premature_certainty_risk: medium
  next_safe_surface: "adapter_contract_implementation_packet"
  promotion_allowed: false
  may_write_memory_now: false
  may_change_retrieval_order_now: false
```

## Admission Bar Before Code

An implementation packet may be opened only if it keeps all of these conditions:

- use synthetic StructMemEval cases only;
- fetch or read cases in a bounded explicit path, not as a transitive runtime
  dependency;
- run without API keys for the first validator;
- avoid importing official runner modules;
- avoid installing `requirements.txt` into AB runtime;
- use an in-memory or temp-directory projection, never the real AB store;
- assert `memory_rows_delta == 0` and `memory_edges_delta == 0`;
- include deterministic family-specific normalizers before any LLM judge;
- produce a review artifact before any durable memory ingest.

The first implementation should be named:

```text
structmemeval_adapter_contract_impl
```

Minimum first implementation scope:

1. Load three pinned sample JSON files by URL or user-provided local path.
2. Validate the common `case_id / sessions[] / queries[]` schema.
3. Build temporary `benchmark_synthetic_event` records in memory only.
4. Emit counts and source hashes.
5. Exit with a no-write proof.

Do not compute benchmark accuracy in that first implementation unless the
deterministic normalizer is already reviewed.

## Verification Command

Use this command before commit:

```bash
git diff --check && rg -n "agent_bridge.structmemeval_fit_packet.v0|no_write_invariant|third_party_runtime_dependencies: false|private_memory_export_allowed: false|promotion_allowed: false" docs/reports/goal-c-u/2026-07-09-structmemeval-fit-packet.md
```

## Decision

Proceed with StructMemEval as AB's first external benchmark fit lane, but only
through a no-write adapter contract.

Do not add a benchmark runner, MCP tool, runtime dependency, DB schema, or
retrieval-policy change in this slice. The next safe step is a separate
`structmemeval_adapter_contract_impl` packet that validates three pinned
synthetic cases and proves the AB store remains untouched.
