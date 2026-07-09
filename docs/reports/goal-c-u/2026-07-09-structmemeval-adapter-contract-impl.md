# StructMemEval Adapter Contract Implementation

Date: 2026-07-09

Source base commit: `62fa6556`

Run type: no-write adapter contract implementation

Parent packet:

- `docs/reports/goal-c-u/2026-07-09-structmemeval-fit-packet.md`

AB planning anchors:

- Durable memory key: `structmemeval_adapter_contract_impl_20260709`
- Forum thread: `design#119`, post `2961`

## Verdict

The first StructMemEval adapter contract implementation is ready as a local
validator. It does not run a benchmark. It only validates StructMemEval-shaped
synthetic cases and proves that the AB store remains unchanged.

## Landed Files

```text
scripts/structmemeval-adapter-contract.py
scripts/verify-structmemeval-adapter-contract.sh
docs/reports/goal-c-u/2026-07-09-structmemeval-adapter-contract-impl.md
```

## Contract

```yaml
schema: agent_bridge.structmemeval_adapter_contract_impl.v0
official_runner_import_allowed: false
third_party_runtime_dependencies: false
api_key_required: false
private_memory_export_allowed: false
writes_ab_store: false
raw_content_in_output: false
memory_rows_delta: 0
memory_edges_delta: 0
semantic_events_delta: 0
```

The helper:

- loads synthetic StructMemEval case JSON from local files or pinned default
  URLs;
- validates `case_id`, `sessions[]`, `messages[]`, `queries[]`, and
  `reference_answer` shape;
- builds temporary in-memory projection summaries for:
  - `benchmark_synthetic_session`;
  - `benchmark_synthetic_event`;
  - `benchmark_synthetic_query`;
- builds temporary relation edges in process only;
- emits counts, source hashes, sample keys, and no-write proof;
- omits raw message/question/reference content from output.

## Verification

Pre-registered verification:

```bash
python3 -m py_compile scripts/structmemeval-adapter-contract.py
bash -n scripts/verify-structmemeval-adapter-contract.sh
scripts/verify-structmemeval-adapter-contract.sh
git diff --check
rg -n "agent_bridge.structmemeval_adapter_contract_impl.v0|memory_rows_delta: 0|memory_edges_delta: 0|semantic_events_delta: 0|official_runner_import_allowed: false|api_key_required: false" scripts docs/reports/goal-c-u/2026-07-09-structmemeval-adapter-contract-impl.md
```

The verifier is offline:

- creates three local synthetic cases for `tree_based`,
  `state_machine_location`, and `accounting`;
- creates a temp SQLite store with one row in `memories`, `memory_edges`, and
  `semantic_events`;
- runs the helper with `--store-db`;
- asserts case/session/turn/query/projection counts;
- asserts `memory_rows_delta == 0`, `memory_edges_delta == 0`, and
  `semantic_events_delta == 0`;
- confirms missing case files fail.

## Belief Clarity Check

```yaml
belief_clarity_check:
  schema: agent_bridge.memory_belief_clarity_diagnostic.v0
  anchor_question: "Based on current memory, what is current task progress and what information is still needed?"
  progress_known:
    - "StructMemEval fit packet selected a no-write adapter contract as the next implementation lane."
    - "The helper validates common case shape and emits projection counts without raw content."
    - "The verifier proves temp AB store row/edge/event deltas remain zero."
  information_missing:
    - "No actual StructMemEval upstream sample was fetched in verifier; verifier is offline by design."
    - "No benchmark accuracy, retrieval hit rate, or answer normalizer exists yet."
    - "No MCP tool or runtime integration is authorized."
  blockers:
    - "Do not claim StructMemEval benchmark performance from this packet."
    - "Do not import official benchmark runner or install requirements.txt."
    - "Do not write projection records into AB memory."
  uncertainty_markers:
    - "Projection edges are structural placeholders, not evidence-support edges."
    - "Default pinned URLs still require network when used outside the verifier."
  premature_certainty_risk: low
  next_safe_surface: "pinned_upstream_sample_smoke_or_normalizer_design"
  promotion_allowed: false
  may_write_memory_now: false
  may_change_retrieval_order_now: false
```

## Decision

Use `scripts/structmemeval-adapter-contract.py` as the local shape/projection
validator for future StructMemEval work.

Do not add a benchmark runner, MCP tool, DB schema, runtime dependency,
retrieval change, or accuracy claim in this slice. The next safe lane is either
a pinned-upstream sample smoke using the same helper or a deterministic
normalizer design packet for one task family.
