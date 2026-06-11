# BioCortex Retrieval Opt-In Experiment Plan

Date: 2026-06-11

## Status

Human authorization recorded for `opt_in_experiment` implementation work only.
Gate skeleton, audit shape, read-only status surface, store-level
request/response contract, read-only dry-run planner, and read-only review
packet consumer implemented. Ordering behavior is not implemented and not
approved.

```json
{
  "schema": "agent_bridge.biocortex_retrieval.opt_in_experiment_plan.v0",
  "approval_state": "opt_in_implementation_authorized",
  "runtime_adapter_approved": false,
  "default_search_order_change_allowed": false,
  "implementation_allowed": true,
  "gate_skeleton_implemented": true,
  "audit_shape_implemented": true,
  "read_only_status_surface_implemented": true,
  "store_contract_implemented": true,
  "dry_run_planner_implemented": true,
  "review_packet_consumer_implemented": true,
  "ordering_behavior_connected": false
}
```

Machine-readable fixture:

- `docs/design/fixtures/biocortex-retrieval-opt-in-experiment-plan-2026-06-11.json`

Authorization request packet:

- `docs/design/BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_REQUEST_2026_06_11.md`
- `scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh`

Authorization decision:

- `docs/design/BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_DECISION_2026_06_11.md`
- `docs/design/fixtures/biocortex-retrieval-opt-in-authorization-decision-2026-06-11.json`

## Experiment Shape

The first acceptable experiment is FTS-only and explicit opt-in:

- affected mode: `SqliteStore::memory_search`;
- exact call site: `crates/store/src/sqlite.rs:3067`;
- proposed authorization scope: `opt_in_experiment`;
- default calls without opt-in: unchanged baseline order;
- hybrid and semantic modes: not authorized and not modified.

The experiment must be an after-baseline sidecar:

1. Run current FTS `memory_search` and keep the baseline order.
2. Copy only bounded candidate key/content summaries into the BioCortex
   side-signal adapter.
3. Join side-signal rows by candidate key only.
4. If and only if the call is explicitly opted in, produce an experimental
   final order beside the baseline order.
5. Emit audit telemetry with baseline order, experimental order, side-signal
   status, latency, and authorization scope.

BioCortex must not become a candidate recall source.

## Proposed Gates

This plan intentionally does not reuse the shadow enable flag as approval for
order influence. A future implementation would need separate gates:

| gate | proposed value | required behavior |
|---|---|---|
| Cargo feature | `biocortex-retrieval-opt-in` | Builds the optional experiment only. |
| runtime enable | `AB_BIOCORTEX_RETRIEVAL_OPT_IN=1` | Allows opted-in calls to request experimental order. |
| operator disable | `AB_BIOCORTEX_RETRIEVAL_DISABLE=1` | Forces baseline order and skips BioCortex. |
| per-call scope | explicit opt-in argument/session flag | Required for any order influence. |

Both the feature and runtime enable are insufficient without the per-call
opt-in scope.

## Implementation Progress

Slice 1 landed as a gate skeleton:

- Cargo feature: `biocortex-retrieval-opt-in`;
- runtime enable env: `AB_BIOCORTEX_RETRIEVAL_OPT_IN`;
- operator disable env: `AB_BIOCORTEX_RETRIEVAL_DISABLE`;
- report schema: `agent_bridge.biocortex_retrieval.opt_in_gate.v0`;
- implementation stage: `gate_skeleton_only`;
- ordering behavior connected: `false`.

The gate report can say the experiment is ready only when feature, runtime env,
and per-call opt-in are present and the operator disable is absent. Even in that
ready state, it still reports `may_change_search_order_now=false`.

Slice 2 landed the explicit per-call audit shape:

- audit schema: `agent_bridge.biocortex_retrieval.opt_in_call_audit.v0`;
- per-call opt-in source: `explicit_call_argument_reserved`;
- baseline order is represented by hash and count only;
- raw memory keys and memory content are not included;
- experimental order is marked unavailable;
- returned order is explicitly `baseline`;
- fallback reason is always present;
- hybrid and semantic modes are marked unauthorized.

The audit shape is still `audit_shape_only`; it does not run BioCortex, change
candidate recall, or change returned order.

Slice 3 landed read-only status surfaces:

- CLI: `agent-bridge bio-cortex retrieval-opt-in-status`;
- MCP tool: `biocortex_retrieval_opt_in_status`;
- both expose the same opt-in call audit schema;
- both preserve hashed query/order output and no raw memory keys/content;
- both keep `ordering_behavior_connected=false`.

Slice 4 landed the store-level request/response contract:

- contract schema: `agent_bridge.store.memory_search.biocortex_opt_in_contract.v0`;
- request type: `BioCortexRetrievalOptInRequest`;
- decision type: `BioCortexRetrievalOptInDecision`;
- response type: `BioCortexRetrievalOptInResponseContract`;
- only `fts` is mode-authorized;
- baseline completion is explicit and can represent zero-hit baseline results;
- every blocked state returns a baseline response with a fallback reason;
- audit requirements forbid raw query text, raw memory keys, and memory content;
- bridge audit/status includes a `store_contract` summary.

The contract still does not call BioCortex or alter ordering. It gives the
future ordering implementation a typed boundary it must satisfy before any
experimental order can be returned.

Slice 5 landed a read-only dry-run planner:

- CLI: `agent-bridge bio-cortex retrieval-opt-in-dry-run`;
- MCP tool: `biocortex_retrieval_opt_in_dry_run`;
- planner schema: `agent_bridge.biocortex_retrieval.opt_in_dry_run_plan.v0`;
- plans baseline FTS search, candidate projection, side-signal, join/score,
  and return-order steps without executing them;
- includes the store contract response and fallback reason;
- reports `calls_memory_search=false`, `runs_biocortex=false`, and
  `changes_memory_search_order=false`;
- hashes query and baseline order and never includes raw query text, raw memory
  keys, or memory content.

The planner is a preview and review surface only. It does not grant runtime
adapter approval and does not connect ordering behavior.

Slice 6 landed a read-only review packet consumer:

- CLI: `agent-bridge bio-cortex retrieval-opt-in-review-packet`;
- MCP tool: `biocortex_retrieval_opt_in_review_packet`;
- packet schema: `agent_bridge.biocortex_retrieval.opt_in_review_packet.v0`;
- consumes a dry-run plan and copies only safe summary fields;
- does not include the raw dry-run payload;
- reports boundary violations if the plan claims execution, raw data exposure,
  or ordering influence;
- keeps `approval_state=not_approved`, `runtime_adapter_approved=false`, and
  `may_implement_ordering_now=false`.

The review packet consumer is evidence organization only. It can make a dry-run
plan easier to inspect, but it cannot approve runtime influence or connect
ordering behavior.

## Fail-Open Rules

The experiment must return the baseline list for:

- BioCortex checkout absent;
- adapter error;
- adapter timeout;
- side-signal coverage below threshold;
- malformed side-signal row;
- missing explicit opt-in scope;
- `AB_BIOCORTEX_RETRIEVAL_DISABLE=1`.

Every fallback must record why it returned baseline.

## Metrics

Before implementation can be reviewed, the packet must define:

- target corpus and expected labels;
- baseline top-1, MRR, and nDCG;
- experimental top-1, MRR, and nDCG;
- regression count and regression examples;
- p50/p95/p99 side-signal latency;
- p50/p95/p99 added default-path latency;
- fallback rate by reason;
- operator kill-switch latency compared with baseline.

Initial pass thresholds:

| metric | threshold |
|---|---:|
| side-signal coverage | >= 0.8 |
| labeled regression count | 0 for clear-positive gate corpus |
| MRR delta | > 0 on current and hard holdout corpora |
| p95 added default-path latency | <= 20 ms |
| p99 added default-path latency | <= 50 ms |

## Test Requirements

Future implementation review must include tests proving:

- feature disabled: gate reports disabled and no ordering behavior exists;
- runtime enable unset: baseline order is returned;
- per-call opt-in missing: baseline order is returned;
- operator disable set: baseline order is returned even when enabled and
  opted-in;
- missing checkout, adapter error, timeout, low coverage, and malformed rows all
  return baseline;
- FTS opt-in may only affect `SqliteStore::memory_search`;
- hybrid and semantic modes remain unchanged;
- dry-run planner does not call `memory_search` or BioCortex and does not echo
  query or keys;
- review packet consumer does not include the raw dry-run payload, query, keys,
  or content;
- review packet consumer reports boundary violations without approving order
  influence;
- audit telemetry includes baseline order, experimental order, fallback reason,
  latency, and authorization scope.

## Human Review Boundary

This plan can be reviewed as a request for `opt_in_experiment` authorization.
It does not request or imply `default_retrieval_influence_fts`, hybrid, or
semantic authorization.

The human decision recorded in
`BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_DECISION_2026_06_11.md` grants only
implementation work for the opt-in experiment. Runtime adapter approval,
default retrieval influence, and production/default use still require a
separate post-implementation review.
