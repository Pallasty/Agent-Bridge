# BioCortex Retrieval Runtime Boundary

Date: 2026-06-10

## Decision

Human review approved `candidate-strong` as an offline-only BioCortex
retrieval side-signal policy. This document defines the next runtime boundary.

Runtime mutation is still not approved:

```json
{"runtime_adapter_approved": false}
```

The only acceptable follow-up implementation is a shadow/advisory surface that
can inspect baseline retrieval candidates and report BioCortex side-signal
evidence without changing the returned `memory_search` order.

## Non-Goals

- No BioCortex `EmbeddingBackend` registration.
- No call to `set_default_backend` with a BioCortex-backed adapter.
- No automatic online reranking of `memory_search` results.
- No mutation of memory rows, embeddings, coactivation edges, graph edges,
  access counters, rewards, substrate state, or BioCortex plasticity state.
- No background learning loop.
- No hidden dependency on the sibling `biocortex-rs` checkout for default AB
  startup.
- No runtime claim stronger than "advisory side signal" until a separate
  implementation review changes `runtime_adapter_approved`.

## Allowed Runtime Shape

The first runtime-facing shape may be one of:

- a CLI command that accepts an explicit query plus explicit candidate rows and
  prints a side-signal review packet;
- an MCP tool that accepts explicit query/candidate input and returns a
  read-only side-signal report;
- a shadow telemetry path that observes the already-produced baseline search
  page and records only aggregate metrics.

It must not be wired into the normal `memory_search` response path as a ranking
actuator. If it runs near `memory_search`, it must be observe-only: baseline
results are computed, returned, and logged exactly as they would be without
BioCortex.

## Feature And Operator Gates

Default behavior:

- compile-time: disabled by default;
- runtime: disabled by default;
- operator kill switch: always wins.

Proposed gates:

| gate | value | effect |
|---|---|---|
| Cargo feature | `biocortex-retrieval-shadow` | Builds the optional shadow/advisory surface. |
| env enable | `AB_BIOCORTEX_RETRIEVAL_SHADOW=1` | Allows the surface to run. |
| env disable | `AB_BIOCORTEX_RETRIEVAL_DISABLE=1` | Forces baseline-only behavior even if enabled. |
| policy | `AB_BIOCORTEX_RETRIEVAL_ALPHA_POLICY=candidate-strong` | Selects the approved offline policy for reporting. |

`BIOCORTEX_RETRIEVAL_BLEND_ALPHA` remains a diagnostic-only override. Runtime
surfaces may report it, but must mark `explicit_alpha=true` and must not cite it
as an approved gate pass.

## Read-Only Dataflow

Input contract:

```json
{
  "query": "What should Agent-Bridge do next?",
  "candidates": [
    {
      "key": "retrieval_benchmark",
      "content": "BioCortex stays a side signal until it proves value..."
    }
  ]
}
```

Allowed processing:

1. Compute or receive the baseline AB ranking outside the BioCortex path.
2. Send only the query plus explicit candidate key/content pairs to the
   BioCortex side-signal adapter.
3. Receive bounded rows:

```json
{"candidate_key":"retrieval_benchmark","score":0.42,"evidence":"..."}
```

4. Join rows by candidate key in memory.
5. Compute an advisory blended score for the report only.
6. Emit a review payload that includes baseline rank, advisory rank, coverage,
   alpha policy, latency, and `runtime_adapter_approved=false`.

Missing side-signal rows are fail-open to baseline in production surfaces and
fail-closed in review/gate surfaces:

| surface | missing-row behavior |
|---|---|
| baseline `memory_search` | ignore BioCortex completely; return baseline hits |
| CLI/MCP review | return a warning and coverage ratio |
| benchmark gate | fail if coverage drops below the registered threshold |

## Latency SLO

Offline measurements on 2026-06-10 showed 1.342-2.899 ms/query for the current
local corpora. Online behavior must be measured again because process startup,
candidate serialization, and MCP/CLI dispatch may dominate.

Initial runtime SLO:

| metric | target | hard limit |
|---|---:|---:|
| p95 side-signal time for 5 candidates | <= 20 ms/query | 50 ms/query |
| timeout behavior | baseline-only fallback | baseline-only fallback |
| memory_search added latency | 0 ms for default path | BioCortex must not block default search |

The default `memory_search` path must not wait for BioCortex. If a future
shadow observer runs asynchronously, timeout or failure must drop the shadow
sample and keep baseline behavior unchanged.

## Review Surface

Every runtime-facing report must include:

- `schema`;
- `read_only=true`;
- `runtime_adapter_approved=false`;
- `alpha_policy`;
- `blend_alpha`;
- `explicit_alpha`;
- side-signal coverage;
- baseline top key and advisory top key;
- expected-key regressions when the input contains labels;
- latency fields;
- enable/disable gate state;
- clear statement that returned AB retrieval order was not changed.

Suggested schema:

```json
{
  "schema": "agent_bridge.biocortex_retrieval_shadow_report.v0",
  "read_only": true,
  "runtime_adapter_approved": false,
  "alpha_policy": "candidate-strong",
  "blend_alpha": 0.8,
  "explicit_alpha": false,
  "side_signal_coverage": 1.0,
  "latency_ms": 3.2,
  "default_search_order_changed": false
}
```

## Implementation Acceptance Checklist

Before any code implementation can be accepted:

- `cargo check -p ab-bridge --no-default-features` must not require BioCortex,
  Wayland, Seed, or host desktop native dependencies.
- `memory_search` tests must show identical output ordering with the feature
  disabled and with `AB_BIOCORTEX_RETRIEVAL_DISABLE=1`.
- The new surface must be callable only when the compile feature and runtime
  enable gate are both active.
- Any failure in BioCortex side-signal generation must return baseline-only or
  a review warning, never a search failure.
- The report must expose `runtime_adapter_approved=false`.
- Forum and memory notes must record the measured p95 latency and any winner
  changes before considering a stronger runtime design.

## Next Step

Implement, if desired, a review-only CLI/MCP surface behind
`biocortex-retrieval-shadow`. Do not modify `memory_search` ranking. Automatic
reranking requires a separate design with new evidence, new tests, and a new
human approval that explicitly changes `runtime_adapter_approved`.

## Implementation Status

First review-only surface landed on 2026-06-10:

- feature gate: `biocortex-retrieval-shadow`;
- CLI surface: `agent-bridge bio-cortex retrieval-shadow`;
- MCP surface: `biocortex_retrieval_shadow`;
- runtime enable: `AB_BIOCORTEX_RETRIEVAL_SHADOW=1`;
- operator kill switch: `AB_BIOCORTEX_RETRIEVAL_DISABLE=1`;
- schema: `agent_bridge.biocortex_retrieval_shadow_report.v0`.

The surface accepts explicit query/candidate rows and reports baseline rank,
advisory rank, BioCortex side-signal evidence, coverage, alpha policy, latency,
and gate state. It does not call `memory_search`, register an `EmbeddingBackend`,
write AB memory, or change returned retrieval order.

Verification on 2026-06-10:

```bash
CARGO_TARGET_DIR=/tmp/ab-target-biocortex-shadow-default \
cargo check -p ab-bridge --no-default-features

CARGO_TARGET_DIR=/tmp/ab-target-biocortex-shadow-feature \
cargo check -p ab-bridge --no-default-features \
  --features biocortex-retrieval-shadow
```

Observed behavior:

- no-feature CLI help does not expose `retrieval-shadow`;
- feature build exposes `bio-cortex retrieval-shadow`;
- default runtime state returns `status=runtime_disabled`;
- `AB_BIOCORTEX_RETRIEVAL_SHADOW=1` returns `status=ok` on the first retrieval
  gate corpus row with `side_signal_coverage=1.0`;
- `AB_BIOCORTEX_RETRIEVAL_DISABLE=1` wins over enable and returns
  `status=operator_disabled`;
- every path keeps `runtime_adapter_approved=false` and
  `default_search_order_changed=false`.

Focused tests added on 2026-06-10:

- `retrieval_boundary_payload_keeps_runtime_mutation_forbidden`;
- `retrieval_rank_report_is_advisory_even_when_side_signal_changes_top`;
- `biocortex_retrieval_shadow_schema_is_explicit_and_readonly`.

Targeted commands:

```bash
CARGO_INCREMENTAL=0 \
CARGO_TARGET_DIR=/tmp/ab-target-biocortex-shadow-lib-tests \
cargo test -p ab-bridge --lib --no-default-features \
  biocortex_shadow::tests::retrieval_ -- --nocapture

CARGO_INCREMENTAL=0 \
CARGO_TARGET_DIR=/tmp/ab-target-biocortex-shadow-feature-lib-tests \
cargo test -p ab-bridge --lib --no-default-features \
  --features biocortex-retrieval-shadow \
  biocortex_retrieval_shadow_schema_is_explicit_and_readonly -- --nocapture
```

Both targeted `--lib` test runs passed. A broader `cargo test -p ab-bridge`
attempt was intentionally abandoned after integration-test linking exhausted
the temporary disk quota; it did not expose a code assertion failure.
