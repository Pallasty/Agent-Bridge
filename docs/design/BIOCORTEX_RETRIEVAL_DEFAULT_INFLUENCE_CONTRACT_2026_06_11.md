# BioCortex Retrieval Default Influence Contract

Date: 2026-06-11

## Status

Design contract only. Not implemented. Not approved.

```json
{
  "runtime_adapter_approved": false,
  "default_search_order_change_allowed": false,
  "human_authorization_scope": "none"
}
```

This document defines the minimum contract for any future proposal that asks
BioCortex to influence default Agent-Bridge retrieval order. It is not a request
to implement that influence.

## Current Non-Implementation

The current BioCortex retrieval surface is still shadow-only:

- it accepts explicit query/candidate rows;
- it reports advisory side-signal evidence;
- it does not call default `memory_search`;
- it does not register an `EmbeddingBackend`;
- it does not write memory, graph edges, embeddings, coactivation, rewards, or
  approval state;
- it keeps `runtime_adapter_approved=false`;
- it keeps `default_search_order_changed=false`.

## Exact Future Call Sites

Any future default-order influence proposal must name which call site it
changes and must leave all other retrieval modes untouched unless they are also
explicitly named in the human authorization.

| mode | file | line | function | current status |
|---|---|---:|---|---|
| FTS | `crates/store/src/sqlite.rs` | 3067 | `SqliteStore::memory_search` | not modified |
| Hybrid | `crates/store/src/sqlite.rs` | 3228 | `SqliteStore::memory_search_hybrid` | not modified |
| Semantic | `crates/store/src/sqlite.rs` | 5585 | `SqliteStore::memory_search_semantic` | not modified |

The trait contract lives in `crates/store/src/lib.rs`:

- `StateStore::memory_search`
- `StateStore::memory_search_hybrid`
- `StateStore::memory_search_semantic`

## Allowed Future Shape

A future implementation, if approved, must be an after-baseline sidecar stage:

1. Compute the baseline result list exactly as today.
2. Clone only bounded candidate key/content summaries for the side-signal
   adapter.
3. Apply a short timeout.
4. Join side-signal rows by candidate key only.
5. Produce either the original baseline list or an explicitly authorized
   reordered list.
6. Emit audit telemetry comparing baseline and final order.

BioCortex must never become the source of candidate recall for default
`memory_search`. It may only influence ordering of candidates already retrieved
by the existing AB path, and only after explicit authorization.

## Fail-Open Contract

Default retrieval must return the baseline list in every failure case below:

| condition | required behavior |
|---|---|
| BioCortex checkout missing | return baseline list; record `side_signal_status=absent` |
| adapter binary/example fails | return baseline list; record `side_signal_status=error` |
| timeout reached | return baseline list; record `side_signal_status=timeout` |
| partial coverage below threshold | return baseline list; record `side_signal_status=coverage_below_threshold` |
| malformed side-signal row | ignore malformed row; if coverage falls below threshold, return baseline |
| operator kill switch set | skip BioCortex entirely; return baseline list |

The operator kill switch must win over every enable flag:

```bash
AB_BIOCORTEX_RETRIEVAL_DISABLE=1
```

## Latency Guardrails

Default-path latency must be measured separately from shadow side-signal
latency. A future implementation must report:

- baseline p50/p95/p99 for each affected mode;
- enabled p50/p95/p99 for each affected mode;
- delta p50/p95/p99;
- timeout count;
- fallback count;
- side-signal coverage distribution.

Initial guardrail for any opt-in experiment:

| metric | limit |
|---|---:|
| default p95 added latency | <= 20 ms |
| default p99 added latency | <= 50 ms |
| timeout fallback | baseline list, no search failure |
| kill-switch latency | equivalent to baseline within noise |

If a corpus or host cannot meet these limits, the experiment must stay
shadow-only on that host.

## Test Requirements

Before asking for human authorization, a future implementation must add tests
that prove:

- with the feature disabled, result order is byte-for-byte identical to current
  baseline;
- with runtime enable unset, result order is identical to baseline;
- with `AB_BIOCORTEX_RETRIEVAL_DISABLE=1`, result order is identical to baseline
  even when runtime enable is set;
- missing BioCortex checkout returns baseline;
- adapter error returns baseline;
- timeout returns baseline;
- partial coverage below threshold returns baseline;
- authorized opt-in mode can change order only for the named call site;
- audit output includes baseline order, final order, side-signal status,
  latency, and authorization scope.

## Authorization Scope

Human authorization must name the exact scope:

- `opt_in_experiment`: may affect only explicitly opted-in calls or sessions;
- `default_retrieval_influence_fts`: may affect `SqliteStore::memory_search`;
- `default_retrieval_influence_hybrid`: may affect
  `SqliteStore::memory_search_hybrid`;
- `default_retrieval_influence_semantic`: may affect
  `SqliteStore::memory_search_semantic`.

Authorization for one mode does not imply authorization for another mode.

## Current Recommendation

Do not implement default retrieval influence yet. The next acceptable work is a
non-mutating design review packet that references this contract, the runtime
boundary proof, and a proposed opt-in experiment plan.

The current proposed opt-in experiment plan is:

- `docs/design/BIOCORTEX_RETRIEVAL_OPT_IN_EXPERIMENT_PLAN_2026_06_11.md`
- `docs/design/fixtures/biocortex-retrieval-opt-in-experiment-plan-2026-06-11.json`
