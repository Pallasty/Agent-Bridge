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
and semantic paths remain unchanged. A focused controlled-trial runner now
emits aggregate-backed review-request evidence for commit
`34bf2e3a3ee74135f6774381c094e3ad64bb2289`; the durable review request remains
request-only and grants no runtime influence. A separate authorization decision
now grants only explicit opt-in FTS runtime influence while keeping default,
hybrid, and semantic influence unauthorized. Post-decision runtime readiness now
confirms that the formal decision packet can drive the gated store/readiness
chain to `ready_for_controlled_explicit_opt_in_fts_trial` without changing
default retrieval order. A follow-up post-runtime-evidence-backed decision
packet now tightens that chain so the final readiness/gate/status surfaces all
report `post_runtime_evidence_summary_ready=true`. A non-production
live-candidate fixture then proves that the post-runtime-backed final gate can
run BioCortex and move the protected explicit opt-in FTS order while default
retrieval remains unchanged. A reusable post-runtime live-candidate runner now
replays that proof end-to-end and emits checked redacted artifacts without
manual command assembly. The same runner now has a multi-case fixture that
observes three protected explicit opt-in order movements across three batch
query cases. A semantic-diverse corpus runner now replays four independent
non-production fixture cases across isolated stores, producing eight protected
BioCortex movements with default retrieval still unchanged. The aio2 handoff
review for that semantic-diverse corpus is now recorded and accepts the
evidence for selecting a downstream AIO integration checkpoint, without
granting default, hybrid, semantic, approval-write, or production-use
permission. The first downstream checkpoint is now selected as the Semantic
System Bus LSWR action/result runtime-evidence checkpoint. The ready downstream
AIO runtime-evidence handoff packet is now connected to a read-only SSB/LSWR
action-result review fixture, and a read-only SSB adapter fixture now projects
the handoff into a conservative `not_verified` SSB action-result shape. A live
read-only LSWR `world_visibility_query` runtime observation was then collected:
the MCP tool is present, but the loopback LSWR host was unreachable, so the
runtime action result remains `not_verified`. A follow-up one-shot loopback
fixture host now proves that the MCP `world_visibility_query` surface can
return a `verified` `agent_bridge.semantic_bus.action_result.v0` wrapper when a
loopback host responds. This is fixture-host evidence only; a real onsen live
root viewport still must be attached before the result can be treated as real
LSWR runtime evidence. A host-attach preflight then confirmed that this Linux
checkout does not currently have the accepted onsen Step B runtime checkout or a
listener on `127.0.0.1:37691`.

```json
{
  "schema": "agent_bridge.biocortex_retrieval.opt_in_experiment_plan.v0",
  "status": "loopback_lswr_host_attach_preflight_blocked",
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
  "controlled_trial_runner_implemented": true,
  "controlled_trial_runner_clean_worktree_verified": true,
  "runtime_influence_review_request_summary_landed": true,
  "runtime_influence_authorization_decision_landed": true,
  "post_decision_runtime_readiness_recorded": true,
  "post_runtime_evidence_backed_decision_recorded": true,
  "post_runtime_live_candidate_fixture_recorded": true,
  "post_runtime_live_candidate_runner_landed": true,
  "post_runtime_live_candidate_runner_verified": true,
  "post_runtime_multi_case_live_candidate_fixture_recorded": true,
  "post_runtime_multi_case_live_candidate_evidence_ready": true,
  "post_runtime_semantic_diverse_live_candidate_corpus_recorded": true,
  "post_runtime_semantic_diverse_live_candidate_evidence_ready": true,
  "post_semantic_diverse_review_recorded": true,
  "post_semantic_diverse_review_ready": true,
  "downstream_aio_integration_checkpoint_selected": true,
  "downstream_aio_runtime_evidence_handoff_ready": true,
  "ssb_lswr_action_result_review_fixture_ready": true,
  "read_only_ssb_adapter_fixture_ready": true,
  "live_lswr_action_result_runtime_evidence_observed_not_verified": true,
  "loopback_lswr_action_result_verified_fixture_host_observed": true,
  "loopback_lswr_host_attach_preflight_blocked": true,
  "controlled_explicit_opt_in_fts_trial_ready": true,
  "post_runtime_evidence_backed_controlled_trial_ready": true,
  "post_runtime_live_candidate_evidence_ready": true,
  "explicit_opt_in_fts_runtime_influence_authorized": true,
  "ordering_behavior_connected": false,
  "explicit_opt_in_fts_ordering_behavior_connected": true,
  "explicit_opt_in_fts_runtime_adapter_connected": true
}
```

Machine-readable fixture:

- `docs/design/fixtures/biocortex-retrieval-opt-in-experiment-plan-2026-06-11.json`

Runtime-influence review request summary:

- `docs/design/BIOCORTEX_RETRIEVAL_RUNTIME_INFLUENCE_REVIEW_REQUEST_2026_06_13.md`
- `docs/design/fixtures/biocortex-retrieval-runtime-influence-review-request-summary-2026-06-13.json`

Runtime-influence authorization decision:

- `docs/design/BIOCORTEX_RETRIEVAL_RUNTIME_INFLUENCE_AUTHORIZATION_DECISION_2026_06_13.md`
- `docs/design/fixtures/biocortex-retrieval-runtime-influence-authorization-decision-2026-06-13.json`

Post-runtime live-candidate runner:

- `scripts/run-biocortex-post-runtime-live-candidate.sh`
- `docs/design/BIOCORTEX_RETRIEVAL_POST_RUNTIME_LIVE_CANDIDATE_RUNNER_2026_06_13.md`
- `docs/design/fixtures/biocortex-retrieval-post-runtime-live-candidate-runner-2026-06-13.json`

Post-runtime multi-case live-candidate fixture:

- `docs/design/BIOCORTEX_RETRIEVAL_POST_RUNTIME_MULTI_CASE_LIVE_CANDIDATE_2026_06_13.md`
- `docs/design/fixtures/biocortex-retrieval-post-runtime-multi-case-live-candidate-fixture-2026-06-13.json`
- `docs/design/fixtures/biocortex-retrieval-post-runtime-multi-case-live-candidate-2026-06-13.json`

Post-runtime semantic-diverse live-candidate corpus:

- `scripts/run-biocortex-post-runtime-semantic-diverse-live-candidate-corpus.sh`
- `docs/design/BIOCORTEX_RETRIEVAL_POST_RUNTIME_SEMANTIC_DIVERSE_LIVE_CANDIDATE_2026_06_14.md`
- `docs/design/fixtures/biocortex-retrieval-post-runtime-semantic-diverse-live-candidate-corpus-2026-06-14.json`
- `docs/design/fixtures/biocortex-retrieval-post-runtime-semantic-diverse-live-candidate-2026-06-14.json`

Post-semantic-diverse review:

- `docs/design/BIOCORTEX_RETRIEVAL_POST_SEMANTIC_DIVERSE_REVIEW_2026_06_15.md`
- `docs/design/fixtures/biocortex-retrieval-post-semantic-diverse-review-2026-06-15.json`

Downstream AIO checkpoint selection:

- `docs/design/BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_CHECKPOINT_SELECTION_2026_06_15.md`
- `docs/design/fixtures/biocortex-retrieval-downstream-aio-checkpoint-selection-2026-06-15.json`

Downstream AIO runtime-evidence handoff:

- `docs/design/BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_RUNTIME_EVIDENCE_HANDOFF_2026_06_15.md`
- `docs/design/fixtures/biocortex-retrieval-downstream-aio-runtime-evidence-handoff-2026-06-15.json`

SSB/LSWR action-result review fixture:

- `docs/design/BIOCORTEX_RETRIEVAL_SSB_LSWR_ACTION_RESULT_REVIEW_FIXTURE_2026_06_15.md`
- `docs/design/fixtures/biocortex-retrieval-ssb-lswr-action-result-review-fixture-2026-06-15.json`

Read-only SSB adapter fixture:

- `docs/design/BIOCORTEX_RETRIEVAL_READ_ONLY_SSB_ADAPTER_FIXTURE_2026_06_15.md`
- `docs/design/fixtures/biocortex-retrieval-read-only-ssb-adapter-fixture-2026-06-15.json`

Live LSWR action-result runtime evidence:

- `docs/design/BIOCORTEX_RETRIEVAL_LIVE_LSWR_ACTION_RESULT_RUNTIME_EVIDENCE_2026_06_15.md`
- `docs/design/fixtures/biocortex-retrieval-live-lswr-action-result-runtime-evidence-2026-06-15.json`

Loopback LSWR action-result verified fixture-host probe:

- `docs/design/BIOCORTEX_RETRIEVAL_LOOPBACK_LSWR_ACTION_RESULT_VERIFIED_PROBE_2026_06_15.md`
- `docs/design/fixtures/biocortex-retrieval-loopback-lswr-action-result-verified-probe-2026-06-15.json`

Loopback LSWR host attach preflight:

- `docs/design/BIOCORTEX_RETRIEVAL_LOOPBACK_LSWR_HOST_ATTACH_PREFLIGHT_2026_06_15.md`
- `docs/design/fixtures/biocortex-retrieval-loopback-lswr-host-attach-preflight-2026-06-15.json`

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

- CLI: `agent-bridge bio-cortex retrieval-opt-in-store-trial`;
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

Slice 22 added a redacted batch diagnostics artifact over the same protected
store trial:

- CLI: `agent-bridge bio-cortex retrieval-opt-in-batch-diagnostics`;
- CLI accepts reusable query-case JSON via `--query-cases-json`;
- MCP tool: `biocortex_retrieval_opt_in_batch_diagnostics`;
- packet schema:
  `agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0`;
- implementation stage: `store_opt_in_batch_diagnostics`;
- query-case fixture:
  `docs/design/fixtures/biocortex-retrieval-opt-in-batch-diagnostic-queries-2026-06-12.json`;
- each query reuses the protected store-trial gate, including the runtime
  influence decision packet, `per_call_opt_in`, feature/env gates, baseline
  recall, side-signal coverage threshold, and fail-open behavior;
- output includes query hashes, baseline/returned order hashes, top key hashes,
  counts, coverage, latency, bucket summaries, and movement classes only;
- raw query text, memory keys, memory contents, raw side-signal rows, and the
  runtime decision packet body are not returned;
- the artifact is read-only and does not mutate AB memory, write approval state,
  register an embedding backend, or authorize default retrieval influence.

Slice 23 added a controlled non-production order-movement fixture:

- CLI:
  `agent-bridge bio-cortex retrieval-opt-in-controlled-order-fixture`;
- fixture:
  `docs/design/fixtures/biocortex-retrieval-opt-in-controlled-order-fixture-2026-06-12.json`;
- run schema:
  `agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0`;
- the command refuses to run unless `AGENT_BRIDGE_DB` is explicitly set away
  from the default store and `--allow-non-production-store-writes` is passed;
- it seeds only fixture memories into the caller-selected non-production store,
  then runs the existing protected batch diagnostics path;
- the fixture uses an FTS `OR` query so baseline recall can include both a
  high-importance one-term match and a lower-importance multi-term match, while
  the BioCortex side-signal can prefer the broader query-term coverage;
- expected evidence is at least one `experimental_moved_order` row with
  `actual_order_changed_count >= 1`, `experimental_source_count >= 1`, and
  `side_signal_ok_count >= 1`;
- output remains redacted: raw queries, memory keys, memory contents, raw
  side-signal rows, and the runtime decision packet body are not returned;
- default `memory_search`, hybrid search, semantic search, approval state, and
  embedding backend registration remain unchanged.

Slice 24 added a redacted post-runtime evidence summary:

- CLI: `agent-bridge bio-cortex retrieval-opt-in-evidence-summary`;
- packet schema:
  `agent_bridge.biocortex_retrieval.opt_in_evidence_summary.v0`;
- implementation stage: `post_runtime_evidence_summary`;
- consumes a redacted batch diagnostics JSON and a redacted controlled order
  fixture run JSON, but does not include either input body in the output;
- reports schema checks, count summaries, raw-safety checks, controlled fixture
  movement, and a review-state recommendation only;
- separates runtime adapter connection/alignment evidence from controlled
  non-production rank-movement evidence;
- reports `recommended_next_step=expand_non_production_corpus` only when the
  controlled movement and redaction checks pass;
- never calls `memory_search`, runs BioCortex, writes approval state, registers
  an embedding backend, or grants default retrieval influence;
- default `memory_search`, hybrid search, semantic search, approval state, and
  embedding backend registration remain unchanged.

Slice 25 added an expanded non-production adapter-coverage fixture:

- fixture:
  `docs/design/fixtures/biocortex-retrieval-opt-in-expanded-controlled-corpus-2026-06-12.json`;
- reuses CLI:
  `agent-bridge bio-cortex retrieval-opt-in-controlled-order-fixture`;
- reuses evidence summary:
  `agent-bridge bio-cortex retrieval-opt-in-evidence-summary`;
- seeds 10 non-production fixture memories across 5 independent query buckets;
- expected evidence is five adapter-allowed, side-signal-ok, experimental-source
  rows, but not additional order movement: the expected
  `actual_order_changed_count` is 0 because this fixture is a broader
  coverage/alignment check rather than a rank-movement proof;
- the separate Slice 23 controlled fixture remains the canonical redacted proof
  that the protected path can produce a returned-order movement;
- output remains redacted: raw queries, memory keys, memory contents, raw
  side-signal rows, and the runtime decision packet body are not returned;
- this fixture is for broader non-production evidence only and does not grant or
  imply runtime/default retrieval influence;
- default `memory_search`, hybrid search, semantic search, approval state, and
  embedding backend registration remain unchanged.

Slice 26 added a redacted evidence aggregate:

- CLI:
  `agent-bridge bio-cortex retrieval-opt-in-redacted-evidence-aggregate`;
- packet schema:
  `agent_bridge.biocortex_retrieval.opt_in_redacted_evidence_aggregate.v0`;
- implementation stage: `post_runtime_redacted_evidence_aggregate`;
- consumes two redacted controlled fixture run JSON files: the Slice 23
  canonical movement run and the Slice 25 expanded adapter-coverage run;
- does not include either input body in the output, only schema/count/safety
  summaries and an interpretation block;
- reports aggregate readiness only when controlled rank movement is observed
  and expanded coverage is observed without additional returned-order movement;
- reports `recommended_next_step=prepare_human_runtime_influence_review_request`
  only when the aggregate is ready;
- never calls `memory_search`, runs BioCortex, writes approval state, registers
  an embedding backend, or grants default retrieval influence;
- default `memory_search`, hybrid search, semantic search, approval state, and
  embedding backend registration remain unchanged.

Slice 27 wired the redacted evidence aggregate into the runtime-influence review
request as optional evidence:

- CLI:
  `agent-bridge bio-cortex retrieval-opt-in-runtime-influence-review-request`
  now accepts optional `--redacted-evidence-aggregate-json`;
- MCP tool:
  `biocortex_retrieval_opt_in_runtime_influence_review_request` now accepts
  optional `redacted_evidence_aggregate`;
- when provided, the request validates that the aggregate is read-only,
  aggregate-ready, redacted, review-only, default-influence-unready, and still
  requires human review;
- the request copies only schema/readiness/interpretation summaries, never the
  aggregate input body or raw fixture/query/key/content fields;
- the aggregate-backed request remains `approval_state=not_approved`, does not
  grant runtime influence, and does not connect ordering behavior or change
  default search order.

Slice 28 wires the aggregate-backed review request into the runtime-influence
decision packet:

- the decision packet now accepts review requests that carry the redacted
  aggregate evidence summary from Slice 27;
- when aggregate evidence is present, it must be ready, redacted, safe for
  review, default-influence-unready, and marked as requiring human review before
  the packet can authorize explicit opt-in FTS implementation;
- legacy review requests without aggregate evidence remain valid and are marked
  `aggregate_review_evidence_state=not_provided_legacy_compatible`;
- the packet copies only summary booleans/state from the review request and
  still excludes the review request body, decision body, aggregate body, raw
  query, raw keys, content, and human decision text;
- this still does not authorize default search order changes, hybrid retrieval,
  semantic retrieval, approval writes, BioCortex runs, memory search calls, or an
  embedding backend registration.

Slice 29 wires the aggregate-backed decision packet into the downstream store
trial preflight:

- `retrieval-opt-in-store-trial` and `retrieval-opt-in-batch-diagnostics` now
  declare that they accept aggregate-backed runtime-influence decision packets;
- if a decision packet claims aggregate-backed evidence, store-trial preflight
  requires the aggregate evidence summary to be ready, redacted, safe for the
  decision, default-influence-unready, and still human-review-gated;
- legacy decision packets without aggregate evidence remain allowed for the
  bootstrap evidence loop that produces the aggregate in the first place;
- batch diagnostics now surfaces per-query aggregate-backed/legacy preflight
  booleans copied from the store-trial summary;
- no aggregate body, review request body, runtime decision body, raw query, raw
  memory key, memory content, or raw side-signal row is returned.

Slice 30 adds a read-only runtime readiness packet:

- `agent-bridge bio-cortex retrieval-opt-in-runtime-readiness-packet` consumes
  an aggregate-backed runtime-influence decision packet, a store-trial summary,
  and a batch-diagnostics summary;
- it reports `control_plane_ready` separately from `live_probe_state`, so an
  empty live store becomes `control_plane_ready_no_live_candidates` instead of a
  false runtime failure;
- it requires aggregate-backed decision evidence and downstream aggregate
  preflight readiness before controlled explicit opt-in FTS calls are reported
  acceptable;
- it never calls `memory_search`, runs BioCortex, writes approval state,
  registers an embedding backend, or changes default retrieval order;
- it does not include the decision packet body, store-trial body,
  batch-diagnostics body, aggregate body, review request body, human decision
  text, raw query, raw key, memory content, or raw side-signal row.

Slice 31 adds a lightweight controlled-trial runner:

- `scripts/run-biocortex-controlled-trial.sh` extracts the focused controlled
  trial path from the full verifier;
- it builds the baseline-preserving trial/review evidence, implementation
  authorization gate, runtime-influence review/decision packets, movement
  fixture run, expanded-coverage fixture run, and redacted evidence aggregate;
- it writes raw fixture inputs only under the selected output directory's
  `inputs/` subdirectory and runs leak guards over the redacted outputs;
- it emits `controlled-trial-summary.json` and `CONTROLLED_TRIAL_REPORT.md`
  with movement, coverage, aggregate readiness, and default-order safety;
- it uses only caller-selected non-production `AGENT_BRIDGE_DB` paths for
  fixture memory writes;
- it does not write approval state, mutate the default Agent-Bridge DB,
  register an embedding backend, change default retrieval order, or grant
  default influence.

Slice 32 records the aggregate-backed runtime-influence review request:

- the source run is
  `target/biocortex-runtime-review-request-20260613/controlled-trial-summary.json`
  for commit `34bf2e3a3ee74135f6774381c094e3ad64bb2289`;
- the committed review document is
  `docs/design/BIOCORTEX_RETRIEVAL_RUNTIME_INFLUENCE_REVIEW_REQUEST_2026_06_13.md`;
- the committed machine-readable summary is
  `docs/design/fixtures/biocortex-retrieval-runtime-influence-review-request-summary-2026-06-13.json`;
- the review request is ready and aggregate-backed, but still has
  `implementation_allowed=false`, `runtime_adapter_approved=false`,
  `default_search_order_change_allowed=false`, and
  `this_packet_grants_request=false`;
- the controlled-trial runner was verified from a clean temporary worktree
  after helper script calls were changed to explicit `bash` invocation.

Slice 33 records the separate runtime-influence authorization decision:

- the committed decision document is
  `docs/design/BIOCORTEX_RETRIEVAL_RUNTIME_INFLUENCE_AUTHORIZATION_DECISION_2026_06_13.md`;
- the committed decision fixture is
  `docs/design/fixtures/biocortex-retrieval-runtime-influence-authorization-decision-2026-06-13.json`;
- the authorized scope is exactly `explicit_opt_in_fts_runtime_influence`;
- the decision authorizes runtime adapter use and ordering connection only for
  explicit per-call FTS opt-in paths;
- the formal decision fixture was consumed by
  `retrieval-opt-in-runtime-influence-decision-packet`, producing
  `target/biocortex-runtime-influence-decision-20260613/runtime-influence-decision-packet.json`;
- it still keeps `default_search_order_change_allowed=false`,
  `default_retrieval_influence_authorized=false`,
  `hybrid_retrieval_influence_authorized=false`, and
  `semantic_retrieval_influence_authorized=false`;
- the decision packet consumer must still produce a read-only control-plane
  packet before downstream store-trial or runtime-readiness evidence is treated
  as authorized.

Slice 34 records post-decision runtime readiness:

- the committed readiness document is
  `docs/design/BIOCORTEX_RETRIEVAL_POST_DECISION_RUNTIME_READINESS_2026_06_13.md`;
- the committed machine-readable summary is
  `docs/design/fixtures/biocortex-retrieval-post-decision-runtime-readiness-2026-06-13.json`;
- the source decision packet is
  `target/biocortex-runtime-influence-decision-20260613/runtime-influence-decision-packet.json`;
- the local evidence directory is
  `target/biocortex-post-decision-readiness-20260613`;
- `retrieval-opt-in-runtime-readiness-packet` reports
  `control_plane_ready=true`, `runtime_readiness_ready=true`, and
  `live_probe_state=control_plane_ready_no_live_candidates`;
- `retrieval-opt-in-runtime-transition-gate` reports
  `status=transition_allowed` for `mode=fts` with explicit per-call opt-in;
- the gated store trial consumes the transition gate and calls the protected
  store trial, while the isolated empty store still returns baseline;
- the gated batch diagnostics reports two gate-allowed protected store-trial
  calls and no BioCortex run because the isolated baselines are empty;
- the status surface reports
  `ready_for_controlled_explicit_opt_in_fts_trial` with no blockers;
- default `memory_search`, hybrid search, semantic search, approval state,
  raw query/key/content redaction, and default search order remain unchanged.

Slice 35 records a post-runtime-evidence-backed decision/readiness chain:

- the committed document is
  `docs/design/BIOCORTEX_RETRIEVAL_POST_RUNTIME_EVIDENCE_BACKED_DECISION_2026_06_13.md`;
- the committed machine-readable summary is
  `docs/design/fixtures/biocortex-retrieval-post-runtime-evidence-backed-decision-2026-06-13.json`;
- the local evidence directory is
  `target/biocortex-post-runtime-evidence-20260613`;
- `retrieval-opt-in-evidence-summary` reports
  `review_state=post_runtime_evidence_ready`,
  `runtime_readiness_requirement_met=true`, and
  `readiness_gated_batch_evidence_ready=true`;
- the follow-up runtime-influence review request reports
  `post_runtime_evidence_summary_ready=true` while still granting nothing;
- the follow-up runtime-influence decision packet reports
  `post_runtime_evidence_summary_backed_review_request=true`,
  `post_runtime_evidence_summary_ready=true`, and
  `post_runtime_evidence_summary_state=post_runtime_evidence_ready`;
- downstream store trial, readiness packet, transition gate, gated store, gated
  batch, and status surfaces were replayed with the post-runtime-backed
  decision packet;
- the final status surface again reports
  `ready_for_controlled_explicit_opt_in_fts_trial`, now with
  `post_runtime_evidence_summary_ready=true`;
- default `memory_search`, hybrid search, semantic search, approval writes,
  raw query/key/content redaction, and default search order remain unchanged.

Slice 36 records a non-production live-candidate fixture under the
post-runtime-backed final gate:

- the committed document is
  `docs/design/BIOCORTEX_RETRIEVAL_POST_RUNTIME_LIVE_CANDIDATE_FIXTURE_2026_06_13.md`;
- the committed machine-readable summary is
  `docs/design/fixtures/biocortex-retrieval-post-runtime-live-candidate-fixture-2026-06-13.json`;
- the local evidence directory is
  `target/biocortex-post-runtime-live-candidate-20260613`;
- the controlled fixture seeded two non-production memories and met expected
  movement evidence;
- the final gated store trial consumed the post-runtime-backed transition gate,
  saw two baseline candidates, allowed the runtime adapter, received
  side-signal status `ok`, ran BioCortex, and returned an experimental order;
- the final gated batch diagnostics reports one query, zero empty baselines,
  one adapter-allowed side-signal-ok row, one BioCortex run, and one actual
  order movement;
- the live-candidate evidence summary reports
  `review_state=post_runtime_evidence_ready`,
  `batch_diagnostic_class=movement_observed`, and
  `evidence_ready=true`;
- `retrieval-opt-in-status` intentionally reports this live-candidate artifact
  set as blocked because controlled-readiness status accepts no-order-change
  readiness evidence, while this fixture proves protected opt-in order movement;
- default `memory_search`, hybrid search, semantic search, approval writes,
  raw query/key/content redaction, and default search order remain unchanged.

Slice 37 adds a reusable post-runtime live-candidate runner:

- script:
  `scripts/run-biocortex-post-runtime-live-candidate.sh`;
- committed document:
  `docs/design/BIOCORTEX_RETRIEVAL_POST_RUNTIME_LIVE_CANDIDATE_RUNNER_2026_06_13.md`;
- committed machine-readable summary:
  `docs/design/fixtures/biocortex-retrieval-post-runtime-live-candidate-runner-2026-06-13.json`;
- local evidence directory:
  `target/biocortex-post-runtime-live-candidate-runner-20260613`;
- the runner consumes the post-runtime decision/readiness/transition packets,
  seeds the canonical controlled fixture into a caller-selected non-production
  DB, runs the gated store trial, gated batch diagnostics, status surface, and
  evidence summary, then verifies every redacted output with `jq`;
- the runner summary reports
  `status=post_runtime_live_candidate_evidence_ready`,
  `runs_biocortex=true`, protected opt-in order movement, and
  `review_state=post_runtime_evidence_ready`;
- the status surface remains side-effect free and intentionally reports
  `blocked` for this movement artifact set;
- runner summary/report leak guards passed for raw query text, raw memory keys,
  memory contents, and raw side-signal rows;
- default `memory_search`, hybrid search, semantic search, approval writes,
  raw query/key/content redaction, and default search order remain unchanged.

Slice 38 adds a multi-case post-runtime live-candidate fixture:

- committed fixture:
  `docs/design/fixtures/biocortex-retrieval-post-runtime-multi-case-live-candidate-fixture-2026-06-13.json`;
- committed document:
  `docs/design/BIOCORTEX_RETRIEVAL_POST_RUNTIME_MULTI_CASE_LIVE_CANDIDATE_2026_06_13.md`;
- committed machine-readable summary:
  `docs/design/fixtures/biocortex-retrieval-post-runtime-multi-case-live-candidate-2026-06-13.json`;
- local evidence directory:
  `target/biocortex-post-runtime-multi-case-live-candidate-20260613`;
- the reusable live-candidate runner replayed the fixture and reported
  `status=post_runtime_live_candidate_evidence_ready`;
- the controlled fixture summary reports `query_count=3`,
  `runs_biocortex_count=3`, and `actual_order_changed_count=3`;
- the gated batch summary reports `query_count=3`,
  `runs_biocortex_count=3`, `baseline_empty_count=0`, and
  `actual_order_changed_count=3`;
- the status surface remains side-effect free and intentionally reports
  `blocked` for this movement artifact set;
- runner summary/report leak guards passed for raw query text, raw memory keys,
  memory contents, and raw side-signal rows;
- default `memory_search`, hybrid search, semantic search, approval writes,
  raw query/key/content redaction, and default search order remain unchanged.

## Post-Semantic-Diverse Review

Slice 40 records the aio2 handoff review for the semantic-diverse corpus:

- committed document:
  `docs/design/BIOCORTEX_RETRIEVAL_POST_SEMANTIC_DIVERSE_REVIEW_2026_06_15.md`;
- committed machine-readable review:
  `docs/design/fixtures/biocortex-retrieval-post-semantic-diverse-review-2026-06-15.json`;
- accepted source status:
  `post_runtime_semantic_diverse_live_candidate_evidence_ready`;
- review status: `post_semantic_diverse_review_recorded`;
- evidence accepted for downstream AIO checkpoint selection: `true`;
- Agent-Bridge fixture expansion complete unless a downstream checkpoint
  exposes a new evidence gap;
- the next project action is
  `select_downstream_aio_integration_checkpoint_for_runtime_backed_evidence`;
- the review does not authorize default retrieval influence, hybrid retrieval
  influence, semantic retrieval influence, approval writes, default
  `memory_search` order changes, production use without a downstream gate, or
  additional raw query/key/content/side-signal disclosure.

## Downstream AIO Checkpoint Selection

Slice 41 selects the first downstream AIO integration checkpoint:

- committed document:
  `docs/design/BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_CHECKPOINT_SELECTION_2026_06_15.md`;
- committed machine-readable selection:
  `docs/design/fixtures/biocortex-retrieval-downstream-aio-checkpoint-selection-2026-06-15.json`;
- selection status: `downstream_aio_integration_checkpoint_selected`;
- selected checkpoint:
  `semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint`;
- selected family: Semantic System Bus / LSWR action-result runtime evidence;
- first consumer: `agent_bridge_semantic_system_bus`;
- direct AiOT runtime consumption selected: `false`;
- first handoff schema:
  `agent_bridge.biocortex_retrieval.downstream_aio_runtime_evidence_handoff.v0`;
- the checkpoint remains read-only and does not authorize default retrieval
  influence, hybrid retrieval influence, semantic retrieval influence,
  approval writes, default `memory_search` order changes, production use,
  direct AiOT runtime consumption, or LSWR action execution from BioCortex
  evidence;
- the prior next project action
  `build_downstream_aio_runtime_evidence_handoff_packet` is completed by
  Slice 42.

## Downstream AIO Runtime-Evidence Handoff

Slice 42 implements the read-only downstream AIO runtime-evidence handoff
packet:

- committed document:
  `docs/design/BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_RUNTIME_EVIDENCE_HANDOFF_2026_06_15.md`;
- committed machine-readable packet:
  `docs/design/fixtures/biocortex-retrieval-downstream-aio-runtime-evidence-handoff-2026-06-15.json`;
- CLI:
  `agent-bridge bio-cortex retrieval-downstream-aio-runtime-evidence-handoff`;
- handoff schema:
  `agent_bridge.biocortex_retrieval.downstream_aio_runtime_evidence_handoff.v0`;
- handoff status: `ready`;
- selected checkpoint:
  `semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint`;
- target schema family: `agent_bridge.semantic_bus.action_result.v0`;
- recover hint: `proceed_to_read_only_ssb_review`;
- the packet remains read-only and does not call `memory_search`, run
  BioCortex, write approval, change default retrieval order, call AiOT runtime,
  execute LSWR actions, mutate the default Agent-Bridge DB, or include raw
  query/key/content/side-signal/human-decision payloads;
- the prior next project action
  `connect_handoff_packet_to_ssb_lswr_action_result_review_fixture` is completed
  by Slice 43.

## SSB/LSWR Action-Result Review Fixture

Slice 43 connects the handoff to the read-only SSB/LSWR action-result review
fixture:

- committed document:
  `docs/design/BIOCORTEX_RETRIEVAL_SSB_LSWR_ACTION_RESULT_REVIEW_FIXTURE_2026_06_15.md`;
- committed machine-readable fixture:
  `docs/design/fixtures/biocortex-retrieval-ssb-lswr-action-result-review-fixture-2026-06-15.json`;
- fixture schema:
  `agent_bridge.biocortex_retrieval.ssb_lswr_action_result_review_fixture.v0`;
- target contract:
  `agent_bridge.semantic_bus.action_result.v0`;
- status: `ready`;
- the fixture confirms that the BioCortex handoff is comparable against the SSB
  action-result contract, but does not fabricate an LSWR action result;
- fields such as `world_tool`, `action_id`, `subject_id`, `verdict`,
  `verified_to`, `verification_method`, and final SSB `recover` still require a
  future read-only SSB adapter fixture;
- the fixture remains read-only and does not call `memory_search`, run
  BioCortex, write approval, change default retrieval order, call AiOT runtime,
  execute LSWR actions, emit `agent_bridge.semantic_bus.action_result.v0`, or
  include raw query/key/content/side-signal/human-decision payloads;
- the prior next project action
  `build_read_only_ssb_adapter_fixture_from_handoff` is completed by Slice 44.

## Read-Only SSB Adapter Fixture

Slice 44 builds the read-only SSB adapter fixture from the handoff:

- committed document:
  `docs/design/BIOCORTEX_RETRIEVAL_READ_ONLY_SSB_ADAPTER_FIXTURE_2026_06_15.md`;
- committed machine-readable fixture:
  `docs/design/fixtures/biocortex-retrieval-read-only-ssb-adapter-fixture-2026-06-15.json`;
- fixture schema:
  `agent_bridge.biocortex_retrieval.read_only_ssb_adapter_fixture.v0`;
- target contract:
  `agent_bridge.semantic_bus.action_result.v0`;
- status: `ready`;
- the fixture projects the BioCortex handoff into a conservative
  `candidate_action_result` with `verdict=not_verified`,
  `reason=fixture_only_no_lswr_runtime_execution`,
  `recover=inspect_host_or_visibility_evidence`, and `raw_available=false`;
- the candidate is fixture-only and must not be ingested as runtime evidence or
  used for training;
- the fixture remains read-only and does not call `memory_search`, run
  BioCortex, write approval, change default retrieval order, call AiOT runtime,
  execute LSWR actions, emit a runtime SSB action result, or include raw
  query/key/content/side-signal/human-decision payloads;
- the prior next project action
  `collect_live_lswr_action_result_runtime_evidence` is completed by Slice 45
  as a live but `not_verified` observation.

## Live LSWR Action-Result Runtime Evidence

Slice 45 runs the read-only live LSWR action-result probe:

- committed document:
  `docs/design/BIOCORTEX_RETRIEVAL_LIVE_LSWR_ACTION_RESULT_RUNTIME_EVIDENCE_2026_06_15.md`;
- committed machine-readable fixture:
  `docs/design/fixtures/biocortex-retrieval-live-lswr-action-result-runtime-evidence-2026-06-15.json`;
- fixture schema:
  `agent_bridge.biocortex_retrieval.live_lswr_action_result_runtime_evidence.v0`;
- observed tool:
  `world_visibility_query`;
- MCP profile used for the short-lived probe: `all`;
- tool listing result: `world_visibility_query` present with `tools_count=240`;
- endpoint observed: `127.0.0.1:37691`;
- action-result schema:
  `agent_bridge.semantic_bus.action_result.v0`;
- action-result verdict: `not_verified`;
- reason: `world_host_unreachable`;
- `verified_to=null`;
- `recover=inspect_host_or_visibility_evidence`;
- `raw_available=false`;
- because the probe used `include_raw=false`, the returned envelope omitted the
  `host_response` field and no host raw payload was included;
- this is runtime observation evidence, not verified LSWR host evidence, and it
  must not be ingested as a verified runtime result or used for training;
- the observation remains read-only and does not call `memory_search`, run
  BioCortex, write approval, change default retrieval order, call AiOT runtime,
  execute LSWR actions, emit a durable runtime SSB action result, or include raw
  key/content/side-signal/human-decision payloads;
- the prior next project action
  `start_or_attach_loopback_lswr_host_then_rerun_live_action_result_probe` is
  completed by Slice 46 against a controlled loopback fixture host.

## Loopback LSWR Action-Result Verified Probe

Slice 46 reruns the read-only live probe against a one-shot loopback fixture
host:

- committed document:
  `docs/design/BIOCORTEX_RETRIEVAL_LOOPBACK_LSWR_ACTION_RESULT_VERIFIED_PROBE_2026_06_15.md`;
- committed machine-readable fixture:
  `docs/design/fixtures/biocortex-retrieval-loopback-lswr-action-result-verified-probe-2026-06-15.json`;
- fixture schema:
  `agent_bridge.biocortex_retrieval.loopback_lswr_action_result_verified_probe.v0`;
- observed tool:
  `world_visibility_query`;
- MCP profile used for the short-lived probe: `all`;
- tool listing result: `world_visibility_query` present with `tools_count=240`;
- endpoint observed: `127.0.0.1:40003` as an ephemeral single-run port;
- action-result schema:
  `agent_bridge.semantic_bus.action_result.v0`;
- action-result verdict: `verified`;
- reason: `null`;
- `verified_to=onsen_live_root_viewport`;
- `recover=proceed`;
- `raw_available=true`;
- the returned envelope included the fixture host response payload;
- this proves the MCP-to-action-result wrapping path against a controlled
  loopback host, not a real onsen runtime or human-visible root viewport;
- the observation remains read-only and does not call `memory_search`, run
  BioCortex, write approval, change default retrieval order, call AiOT runtime,
  execute LSWR actions, or emit a durable runtime SSB action result;
- the host-attach preflight is recorded by Slice 47.

## Loopback LSWR Host Attach Preflight

Slice 47 checks whether the verified loopback probe can now be rerun against
the intended real onsen Step B host:

- committed document:
  `docs/design/BIOCORTEX_RETRIEVAL_LOOPBACK_LSWR_HOST_ATTACH_PREFLIGHT_2026_06_15.md`;
- committed machine-readable fixture:
  `docs/design/fixtures/biocortex-retrieval-loopback-lswr-host-attach-preflight-2026-06-15.json`;
- fixture schema:
  `agent_bridge.biocortex_retrieval.loopback_lswr_host_attach_preflight.v0`;
- status: `blocked_missing_loopback_host_checkout`;
- intended endpoint: `127.0.0.1:37691`;
- intended protocol: `newline_json_tcp`;
- `world_visibility_query` client surface is present under MCP profile `all`;
- no listener is present on `127.0.0.1:37691`;
- the documented macOS onsen Step B checkout is not present on this Linux host;
- the candidate Linux onsen Step B checkout is not present;
- `prototypes/lswr-web-prototype` exists, but is not the newline-JSON TCP onsen
  world-tool host required by this probe;
- the prior next project action
  `attach_real_onsen_lswr_host_then_collect_verified_live_viewport_action_result`
  is refined to
  `restore_or_clone_onsen_step_b_host_checkout_then_launch_dev_host`;
- source resolution is recorded by Slice 48.

## Onsen Step B Source Resolution

Slice 48 resolves whether the accepted onsen Step B host source is available on
this Linux checkout:

- committed document:
  `docs/design/BIOCORTEX_RETRIEVAL_ONSEN_STEP_B_SOURCE_RESOLUTION_2026_06_15.md`;
- committed machine-readable fixture:
  `docs/design/fixtures/biocortex-retrieval-onsen-step-b-source-resolution-2026-06-15.json`;
- fixture schema:
  `agent_bridge.biocortex_retrieval.onsen_step_b_source_resolution.v0`;
- status: `blocked_missing_onsen_step_b_source`;
- documented worktree:
  `/Users/pallasting/Projects/onsen-hd-live-semantic-phase0`;
- documented branch: `codex/live-semantic-phase0-t1`;
- documented head: `10d58ee`;
- expected endpoint: `127.0.0.1:37691`;
- expected protocol: `newline_json_tcp`;
- no accepted onsen Step B checkout is present on this Linux host;
- no listener is present on `127.0.0.1:37691`;
- obvious GitHub SSH candidates were checked and did not produce a usable
  repository from this environment;
- a read-only recovery probe is ready at
  `scripts/probe-onsen-step-b-host-source.sh`;
- the next project action is refined to
  `provide_or_sync_onsen_step_b_checkout_or_repository_url_then_launch_dev_host`.

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
