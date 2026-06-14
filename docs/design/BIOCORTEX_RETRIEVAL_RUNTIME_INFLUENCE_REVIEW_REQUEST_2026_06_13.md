# BioCortex Retrieval Runtime Influence Review Request

Date: 2026-06-13

## Decision State

This document records a review request for explicit opt-in FTS runtime
influence. It is not an approval and does not grant runtime adapter approval,
connect ordering behavior, or allow default `memory_search` order changes.

Machine-readable summary:

- `docs/design/fixtures/biocortex-retrieval-runtime-influence-review-request-summary-2026-06-13.json`

## Source Run

The evidence was generated for implementation commit
`34bf2e3a3ee74135f6774381c094e3ad64bb2289` with:

```bash
scripts/run-biocortex-controlled-trial.sh \
  --out-dir target/biocortex-runtime-review-request-20260613 \
  --samples 1 \
  --reviewer codex-runtime-review \
  --commit 34bf2e3a3ee74135f6774381c094e3ad64bb2289
```

The run was verified from a clean temporary worktree. The runner now invokes
helper shell scripts through `bash`, so clean checkouts do not depend on local
executable bits for helper scripts.

Generated local evidence:

- `target/biocortex-runtime-review-request-20260613/controlled-trial-summary.json`
- `target/biocortex-runtime-review-request-20260613/15-runtime-influence-review-request-with-aggregate.json`
- `target/biocortex-runtime-review-request-20260613/16-runtime-influence-decision-packet-with-aggregate.json`

The `target/` artifacts are local run evidence and are not committed.

## Evidence Summary

- controlled trial status: `controlled_trial_redacted_evidence_ready`;
- movement fixture observed `actual_order_changed_count=1`;
- expanded coverage fixture ran `query_count=5` and
  `experimental_source_count=5`;
- aggregate evidence is ready, controlled rank movement was observed, and
  expanded coverage did not introduce additional movement;
- default influence remains not ready;
- runtime review request is ready and includes aggregate evidence;
- the request packet explicitly has `this_packet_grants_request=false`.

The run also produced a synthetic runtime-influence decision packet to prove
the downstream gate shape. That packet is test evidence only; it is not a live
approval record and does not write approval state.

## Requested Scope

The review request asks whether a separate authorization may approve only:

- explicit opt-in FTS runtime adapter review;
- explicit opt-in FTS ordering behavior connection review;
- per-call opt-in usage under the `biocortex-retrieval-opt-in` feature and
  `AB_BIOCORTEX_RETRIEVAL_OPT_IN`;
- fail-open behavior to baseline on missing gates, adapter failure, timeout,
  malformed side signal, low coverage, or `AB_BIOCORTEX_RETRIEVAL_DISABLE=1`.

It does not request:

- default retrieval influence;
- hybrid retrieval influence;
- semantic retrieval influence;
- any order change for calls without explicit per-call opt-in.

## Boundary

The review request and summary assert:

- `implementation_allowed=false`;
- `runtime_adapter_approved=false`;
- `default_search_order_change_allowed=false`;
- `default_calls_unchanged=true`;
- `writes_approval=false`;
- `calls_memory_search=false`;
- `runs_biocortex=false`;
- `registers_embedding_backend=false`;
- `changes_memory_search_order=false`;
- `ordering_behavior_connected=false`;
- no raw query, key, content, or raw side-signal data is included in committed
  review material.

## Required Decision

A valid follow-up authorization must be a separate decision artifact using
schema `agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_decision.v0`.
It must explicitly state:

- the authorized scope is `explicit_opt_in_fts_runtime_influence`;
- `default_search_order_change_allowed=false`;
- hybrid and semantic retrieval influence remain unauthorized;
- per-call opt-in remains required;
- fail-open to baseline remains required.

Until that separate decision exists, this request remains review preparation
only.
