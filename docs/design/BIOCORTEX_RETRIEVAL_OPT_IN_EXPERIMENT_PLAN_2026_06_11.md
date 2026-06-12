# BioCortex Retrieval Opt-In Experiment Plan

Date: 2026-06-11

## Status

Human authorization recorded for `opt_in_experiment` implementation work only.
Gate skeleton, audit shape, read-only status surface, store-level
request/response contract, read-only dry-run planner, read-only review packet
consumer, read-only execution packet contract, and baseline-preserving runtime
trial surface, read-only runtime trial review packet, and authorization request
runtime-trial-review evidence hook, and hash-only order-diff review packet
implemented. The authorization request bundle can now optionally include
hash-only order-diff evidence. A separate redacted-order artifact now computes
top-k overlap and per-key rank movement from `key_hash` rows only, and the
authorization request bundle can optionally include its summary-only evidence.
The store layer now has a baseline-preserving opt-in search wrapper with a
redacted audit summary. A read-only authorization decision consumer now turns
the human implementation authorization record into a machine-checkable
implementation-only gate. A read-only post-implementation review gate now
checks whether that implementation-only evidence is ready for a separate human
runtime-influence review, without approving runtime adapter influence or
ordering behavior. A read-only runtime-influence review request packet now
combines the post-implementation review gate and redacted order artifact into a
separate human-review request for explicit opt-in FTS influence, while still
granting no runtime adapter approval and connecting no ordering behavior.
A read-only runtime-influence decision consumer now turns a separate human
runtime review record into a machine-checkable implementation gate for explicit
opt-in FTS runtime adapter/order-connection work only. The decision packet
consumer still does not connect ordering behavior or change any returned order.
The store-level opt-in wrapper now connects an explicit opt-in FTS ordering path
for caller-supplied side-signal rows only when runtime approval, ordering
connection, feature/runtime/per-call gates, coverage, and kill-switch checks all
pass. A protected MCP store-trial path now calls AB store baseline
`memory_search`, runs the external BioCortex side-signal adapter only when a
runtime-influence decision packet and runtime gates authorize it, and feeds the
sanitized side-signal into the store wrapper. Default `memory_search`, hybrid,
and semantic paths remain unchanged.

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
  "execution_packet_contract_implemented": true,
  "runtime_trial_implemented": true,
  "runtime_trial_review_packet_implemented": true,
  "authorization_request_runtime_trial_review_evidence_implemented": true,
  "order_diff_packet_implemented": true,
  "authorization_request_order_diff_evidence_implemented": true,
  "redacted_order_artifact_implemented": true,
  "authorization_request_redacted_order_artifact_evidence_implemented": true,
  "store_opt_in_search_wrapper_implemented": true,
  "authorization_decision_consumer_implemented": true,
  "post_implementation_review_gate_implemented": true,
  "runtime_influence_review_request_implemented": true,
  "runtime_influence_decision_packet_implemented": true,
  "store_opt_in_order_connection_implemented": true,
  "store_opt_in_runtime_adapter_connection_implemented": true,
  "ordering_behavior_connected": false,
  "explicit_opt_in_fts_ordering_behavior_connected": true,
  "explicit_opt_in_fts_runtime_adapter_connected": true
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

Slice 7 landed a read-only execution packet contract:

- CLI: `agent-bridge bio-cortex retrieval-opt-in-execution-packet`;
- MCP tool: `biocortex_retrieval_opt_in_execution_packet`;
- packet schema: `agent_bridge.biocortex_retrieval.opt_in_execution_packet.v0`;
- consumes a review packet and copies only safe summary fields;
- rebuilds the store contract with the explicit per-call opt-in bit;
- defines the protected adapter preflight contract: baseline-only candidate
  recall, candidate-key join, fail-open baseline return, and no raw data in the
  report;
- keeps `execution_allowed=false`, `approval_state=not_approved`,
  `runtime_adapter_approved=false`, and `may_implement_ordering_now=false`.

The execution packet is still a preflight contract only. It does not run the
baseline search, run BioCortex, register an embedding backend, or change
ordering behavior.

Slice 8 landed a baseline-preserving runtime trial surface:

- CLI: `agent-bridge bio-cortex retrieval-opt-in-runtime-trial`;
- MCP tool: `biocortex_retrieval_opt_in_runtime_trial`;
- packet schema: `agent_bridge.biocortex_retrieval.opt_in_runtime_trial.v0`;
- consumes an execution packet and copies only safe summary fields;
- accepts explicit query/candidate rows and does not call `memory_search`;
- runs the external BioCortex side-signal adapter only when the opt-in gate,
  execution-packet preflight, and candidate-count checks pass;
- joins side-signal rows by candidate key and reports only hashed/order-count
  summaries;
- always returns baseline order and keeps `changes_memory_search_order=false`.

The runtime trial is evidence generation only. It may run the side-signal
adapter for an explicitly supplied candidate set, but it still does not approve
runtime influence, register an embedding backend, or connect ordering behavior.

Slice 9 landed a read-only runtime trial review packet:

- CLI: `agent-bridge bio-cortex retrieval-opt-in-runtime-trial-review-packet`;
- MCP tool: `biocortex_retrieval_opt_in_runtime_trial_review_packet`;
- packet schema:
  `agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0`;
- consumes a runtime trial packet and copies only safe summary fields;
- verifies that the trial did not call `memory_search`, register a backend,
  mutate AB memory, echo raw query/key/content, or change returned order;
- reports review readiness for baseline-preserving evidence only;
- keeps `approval_state=not_approved`, `runtime_adapter_approved=false`, and
  `may_implement_ordering_now=false`.

The runtime trial review packet organizes post-implementation evidence. It does
not approve runtime influence and does not request permission to connect
ordering behavior.

Slice 10 landed the authorization request evidence hook:

- script: `scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh`;
- required input:
  `agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0`;
- request evidence path: `evidence.runtime_trial_review_packet`;
- copies only safe summary fields from the runtime trial review packet;
- requires baseline-trial review readiness and zero boundary violations;
- keeps `approval_state=not_approved`, `runtime_adapter_approved=false`, and
  `may_implement_ordering_now=false`.

The authorization request bundle is still review preparation only. Including
runtime trial review evidence does not approve runtime influence or connect
ordering behavior.

Slice 11 landed a hash-only order-diff review packet:

- CLI: `agent-bridge bio-cortex retrieval-opt-in-order-diff-packet`;
- MCP tool: `biocortex_retrieval_opt_in_order_diff_packet`;
- packet schema:
  `agent_bridge.biocortex_retrieval.opt_in_order_diff_packet.v0`;
- consumes either a runtime trial packet or a runtime trial review packet;
- compares baseline order and BioCortex advisory order by order hash, top-key
  hash, and expected-key rank delta only;
- does not include raw order keys, raw query, candidate content, or raw
  side-signal rows;
- explicitly marks top-k overlap and per-key movements unavailable without a
  separate redacted-order artifact;
- keeps returned order as baseline and reports
  `actual_return_order_changed=false`;
- keeps `calls_memory_search=false`, `runs_biocortex=false`,
  `runtime_adapter_approved=false`, and `may_implement_ordering_now=false`.

The order-diff packet answers whether the advisory ordering would differ from
the default baseline ordering, but it remains review evidence only. It does not
authorize runtime influence and does not connect ordering behavior.

Slice 12 extended the authorization request bundle with optional order-diff
evidence:

- script: `scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh`;
- optional input:
  `agent_bridge.biocortex_retrieval.opt_in_order_diff_packet.v0`;
- request evidence path: `evidence.order_diff_packet`;
- preserves backward compatibility when no order-diff packet is supplied;
- copies only safe booleans and rank summary fields: diff readiness,
  comparable hash flags, changed/not-changed flags, expected-key rank delta,
  returned-order source, and unavailable-metric sentinels;
- does not copy raw order keys, raw query, candidate content, raw side-signal
  rows, or the source packet;
- keeps `approval_state=not_approved`, `runtime_adapter_approved=false`,
  `calls_memory_search=false`, `runs_biocortex=false`, and
  `may_implement_ordering_now=false`.

Including order-diff evidence in the request bundle helps review the observed
gap between default baseline order and advisory order. It still does not
approve runtime influence, enable an adapter, or connect ordering behavior.

Slice 13 landed a redacted-order artifact:

- CLI: `agent-bridge bio-cortex retrieval-opt-in-redacted-order-artifact`;
- MCP tool: `biocortex_retrieval_opt_in_redacted_order_artifact`;
- packet schema:
  `agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0`;
- consumes either a runtime trial packet or a runtime trial review packet;
- sanitizes rank rows down to `{key_hash, baseline_rank}` and
  `{key_hash, advisory_rank}` before output;
- computes top-k overlap, rank-delta distribution, and per-key movements from
  redacted rows only;
- does not include raw order keys, raw query, candidate content, raw
  side-signal rows, or the source packet;
- keeps returned order as baseline and reports
  `actual_return_order_changed=false`;
- keeps `calls_memory_search=false`, `runs_biocortex=false`,
  `runtime_adapter_approved=false`, and `may_implement_ordering_now=false`.

The redacted-order artifact answers how much the advisory order differs from
the default baseline order without needing raw keys. It is evidence only and
does not approve runtime influence or connect ordering behavior.

Slice 14 extended the authorization request bundle with optional redacted-order
artifact summary evidence:

- script: `scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh`;
- optional input:
  `agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0`;
- request evidence path: `evidence.redacted_order_artifact`;
- preserves backward compatibility when no redacted-order artifact is supplied;
- copies summary-only metrics: artifact readiness, comparable-row status,
  rank-row counts, top-k overlap counts/Jaccard, rank-delta distribution, and
  per-key movement count;
- does not copy raw order keys, raw query, candidate content, raw side-signal
  rows, `key_hash` values, redacted rank rows, or the source packet;
- keeps `approval_state=not_approved`, `runtime_adapter_approved=false`,
  `calls_memory_search=false`, `runs_biocortex=false`, and
  `may_implement_ordering_now=false`.

Including redacted-order artifact evidence in the request bundle helps review
the shape of ordering differences without exposing per-key identifiers in the
request packet. It still does not approve runtime influence, enable an adapter,
or connect ordering behavior.

Slice 15 landed a store-level opt-in search wrapper:

- method: `StateStore::memory_search_biocortex_opt_in`;
- options type: `BioCortexRetrievalOptInSearchOptions`;
- outcome type: `BioCortexRetrievalOptInSearchOutcome`;
- redacted audit type/schema:
  `BioCortexRetrievalOptInSearchAudit` /
  `agent_bridge.store.memory_search.biocortex_opt_in_search_audit.v0`;
- calls the existing baseline `memory_search` first;
- returns the baseline hit order as both `baseline_hits` and `returned_hits`;
- exposes `redacted_audit()` for review/telemetry without raw query, memory
  keys, or memory content;
- reuses `BioCortexRetrievalOptInRequest` /
  `BioCortexRetrievalOptInResponseContract` for the gate decision;
- keeps `runs_biocortex=false`, `runtime_adapter_approved=false`,
  `changes_memory_search_order=false`, `ordering_behavior_connected=false`,
  and `may_implement_ordering_now=false`.

This is the first store boundary where an explicit per-call opt-in can wrap a
real FTS search path. It still does not connect an ordering path: even when
feature/runtime/per-call gates are present, the wrapper returns baseline until a
separate review authorizes runtime adapter influence and ordering behavior.

Slice 16 landed a read-only authorization decision consumer:

- CLI:
  `agent-bridge bio-cortex retrieval-opt-in-authorization-decision-packet`;
- MCP tool:
  `biocortex_retrieval_opt_in_authorization_decision_packet`;
- packet schema:
  `agent_bridge.biocortex_retrieval.opt_in_authorization_decision_packet.v0`;
- consumes the authorization request summary and the human authorization
  decision record;
- does not include the raw request or decision payload;
- authorizes implementation work only when both records preserve
  `runtime_adapter_approved=false`, `default_search_order_change_allowed=false`,
  FTS-only per-call scope, baseline fallback rules, and post-implementation
  review before use;
- keeps `runtime_adapter_approved=false`, `approval_writes_allowed=false`,
  `writes_approval=false`, `calls_memory_search=false`, `runs_biocortex=false`,
  `changes_memory_search_order=false`, `ordering_behavior_connected=false`, and
  `may_implement_ordering_now=false`.

This makes the recorded human authorization machine-checkable while preserving
the separation between "implementation work is authorized" and "runtime adapter
influence is approved." The latter still requires a separate post-implementation
review and explicit ordering-behavior connection.

Slice 17 landed a read-only post-implementation review gate:

- CLI:
  `agent-bridge bio-cortex retrieval-opt-in-post-implementation-review-gate`;
- MCP tool:
  `biocortex_retrieval_opt_in_post_implementation_review_gate`;
- packet schema:
  `agent_bridge.biocortex_retrieval.opt_in_post_implementation_review_gate.v0`;
- consumes the authorization decision packet summary and opt-in plan summary;
- does not include the raw decision packet or raw opt-in plan payload;
- reports `ready_for_human_runtime_influence_review=true` only when the
  implementation-only authorization evidence is intact, the store wrapper is
  baseline-preserving, and the plan records this review gate;
- keeps `approval_state=not_approved`, `runtime_adapter_approved=false`,
  `approval_writes_allowed=false`, `writes_approval=false`,
  `calls_memory_search=false`, `runs_biocortex=false`,
  `changes_memory_search_order=false`, `ordering_behavior_connected=false`, and
  `may_implement_ordering_now=false`.

This gate is deliberately not a runtime approval. It creates the next review
packet boundary: after implementation exists, a separate human runtime-influence
review still has to decide whether any BioCortex side-signal may affect an
explicitly opted-in return order.

Slice 18 landed a read-only runtime-influence review request:

- CLI:
  `agent-bridge bio-cortex retrieval-opt-in-runtime-influence-review-request`;
- MCP tool:
  `biocortex_retrieval_opt_in_runtime_influence_review_request`;
- packet schema:
  `agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_request.v0`;
- consumes the post-implementation review gate summary and redacted order
  artifact summary;
- does not include the raw gate packet, redacted artifact payload, raw query,
  keys, content, or redacted `key_hash` rows;
- requests separate human review for explicit opt-in FTS runtime influence and
  ordering-behavior connection;
- explicitly keeps default search order changes, hybrid influence, semantic
  influence, and this packet's own approval grant set to `false`;
- keeps `approval_state=not_approved`, `runtime_adapter_approved=false`,
  `approval_writes_allowed=false`, `writes_approval=false`,
  `calls_memory_search=false`, `runs_biocortex=false`,
  `changes_memory_search_order=false`, `ordering_behavior_connected=false`, and
  `may_implement_ordering_now=false`.

This request packet is the handoff artifact for the next human runtime review.
It asks for the review, but it is not the review decision and cannot authorize
runtime adapter influence by itself.

Slice 19 landed a read-only runtime-influence decision consumer:

- CLI:
  `agent-bridge bio-cortex retrieval-opt-in-runtime-influence-decision-packet`;
- MCP tool:
  `biocortex_retrieval_opt_in_runtime_influence_decision_packet`;
- packet schema:
  `agent_bridge.biocortex_retrieval.opt_in_runtime_influence_decision_packet.v0`;
- consumes a runtime-influence review request summary and a separate human
  runtime decision record;
- does not include the raw review request, raw decision payload, human decision
  text, raw query, keys, or content;
- can authorize implementation work for explicit opt-in FTS runtime adapter
  influence and explicit opt-in FTS ordering-behavior connection only when the
  human decision and request both preserve the FTS-only, per-call opt-in,
  baseline-candidate-recall, redacted-audit, kill-switch, and fail-open rules;
- keeps default search order changes, default retrieval influence, hybrid
  influence, and semantic influence unauthorized;
- keeps `approval_writes_allowed=false`, `writes_approval=false`,
  `calls_memory_search=false`, `runs_biocortex=false`,
  `changes_memory_search_order=false`, `ordering_behavior_connected=false`, and
  `this_packet_changes_return_order=false`.

This packet is still not the ordering implementation. It makes the separate
human runtime review machine-checkable, but a later implementation step must
connect the adapter and return-order behavior behind the explicit opt-in gates
and then pass post-connection verification.

Slice 20 landed a store-level explicit opt-in FTS ordering connection:

- method: `StateStore::memory_search_biocortex_opt_in`;
- side-signal input type: `BioCortexRetrievalOptInSideSignal`;
- redacted summary type: `BioCortexRetrievalOptInSideSignalSummary`;
- requires `per_call_opt_in=true`, compile feature enabled, runtime enabled,
  `runtime_adapter_approved=true`, `ordering_behavior_connected=true`, and the
  operator disable env absent before any experimental order can be returned;
- requires side-signal coverage to meet the configured threshold, default `0.8`;
- uses baseline FTS `memory_search` as the only candidate recall source;
- joins side-signal rows by candidate key, blends with the baseline score, and
  returns the experimental order only for the protected wrapper call;
- every missing, malformed, or low-coverage side-signal path fails open to the
  baseline order;
- the redacted audit includes counts, coverage, alpha, and availability only;
  it does not include raw query text, raw memory keys, memory contents, or raw
  side-signal rows.

This connects ordering behavior only for the protected explicit opt-in FTS
wrapper. Default `memory_search` calls, hybrid search, and semantic search remain
unchanged, and default search order changes are still unauthorized.

Slice 21 landed a protected store-level runtime adapter trial:

- MCP tool: `biocortex_retrieval_opt_in_store_trial`;
- packet schema: `agent_bridge.biocortex_retrieval.opt_in_store_trial.v0`;
- implementation stage: `store_opt_in_runtime_adapter_connection`;
- requires a valid
  `agent_bridge.biocortex_retrieval.opt_in_runtime_influence_decision_packet.v0`
  whose summary authorizes explicit opt-in FTS runtime adapter use and ordering
  connection;
- requires `per_call_opt_in=true`, compile feature enabled, runtime env enabled,
  and the operator disable env absent before the external adapter is attempted;
- uses AB store baseline `memory_search` as the only candidate recall source;
- runs `biocortex-rs` only against those baseline candidates and joins rows by
  `candidate_key`;
- calls `StateStore::memory_search_biocortex_opt_in` with sanitized side-signal
  rows and returns the wrapper's redacted audit;
- exposes query/order/key information only as hashes, counts, rank rows, and
  contract summaries; raw query text, memory keys, memory contents, and raw
  side-signal rows are not returned;
- does not mutate AB memory, write approval state, register an embedding backend,
  or authorize default retrieval influence.

This is the first real adapter-to-store-wrapper connection, but it is still an
explicit MCP trial surface. Default `memory_search` calls, hybrid search, and
semantic search remain unchanged.

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
- execution packet contract consumes review packets without including raw
  review payload, query, keys, or content;
- execution packet contract keeps execution disallowed and baseline returned;
- runtime trial runs side-signal only after execution-packet preflight and
  explicit opt-in gates pass;
- runtime trial returns baseline and does not echo query, keys, or content;
- runtime trial fails open for missing checkout, timeout, low coverage, malformed
  rows, missing opt-in, and operator disable;
- runtime trial review packet consumes runtime trial output without including
  raw trial payload, query, keys, or content;
- runtime trial review packet reports boundary violations without approving
  runtime influence;
- authorization request bundle requires runtime trial review evidence and does
  not include raw trial payload, query, keys, content, or side-signal rows;
- order-diff packet compares baseline and advisory hashes without including raw
  order keys or per-key movement rows;
- order-diff packet does not call `memory_search`, run BioCortex, approve
  runtime influence, or change returned order;
- redacted-order artifact computes top-k overlap and per-key movement from
  key-hash rows without including raw order keys;
- redacted-order artifact does not call `memory_search`, run BioCortex, approve
  runtime influence, or change returned order;
- authorization request bundle can optionally include order-diff evidence
  without including raw order keys or approving runtime influence;
- authorization request bundle can optionally include redacted-order artifact
  summaries without copying key hashes or approving runtime influence;
- store opt-in search wrapper returns baseline order and emits redacted audit
  without serializing query, keys, or content;
- authorization decision consumer authorizes implementation only and does not
  approve runtime influence or echo raw request/decision fields;
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
