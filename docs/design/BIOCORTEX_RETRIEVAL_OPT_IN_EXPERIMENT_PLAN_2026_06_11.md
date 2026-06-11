# BioCortex Retrieval Opt-In Experiment Plan

Date: 2026-06-11

## Status

Human authorization recorded for `opt_in_experiment` implementation work only.
Gate skeleton and audit shape implemented. Ordering behavior is not implemented
and not approved.

```json
{
  "schema": "agent_bridge.biocortex_retrieval.opt_in_experiment_plan.v0",
  "approval_state": "opt_in_implementation_authorized",
  "runtime_adapter_approved": false,
  "default_search_order_change_allowed": false,
  "implementation_allowed": true,
  "gate_skeleton_implemented": true,
  "audit_shape_implemented": true,
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
