# Live Semantic World Runtime - Interaction Feedback Runtime Executor Authority Gates

**2026-06-16 - status: design draft / no executor authority**

Parent documents:

- [Interaction feedback protocol](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PROTOCOL_2026_06_15.md)
- [Interaction feedback patch apply request boundary](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_BOUNDARY_2026_06_15.md)
- [Interaction feedback patch apply request boundary acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_BOUNDARY_ACCEPTANCE_2026_06_16.md)
- [Interaction feedback runtime executor design preflight](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_2026_06_16.md)
- [Interaction feedback runtime executor design preflight acceptance](LIVE_SEMANTIC_WORLD_RUNTIME_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_ACCEPTANCE_2026_06_16.md)

Forum anchors:

- `#102` post `#3163`: runtime executor design preflight accepted as
  design-preflight-only.
- `#102` post `#3164`: authority-gate design claim.

## 0. Purpose

The accepted runtime executor design preflight proves only that a ready
patch-apply request can be packaged for design review. It deliberately does not
grant authority to query a live runtime, submit a request, apply a patch,
verify the result, or ingest the outcome.

This document defines the authority gates that must sit after that accepted
preflight before any runtime executor can safely mutate LSWR/Onsen state:

```text
runtime executor design preflight
  -> G1 live runtime lookup gate
  -> G2 operator submission gate
  -> G3 patch application gate
  -> G4 post-apply verification gate
  -> G5 outcome ingestion gate
```

Each gate is independently reviewable. Passing one gate must not imply that
later gates are ready or that mutation already happened.

## 1. Core Invariants

All gates must preserve these invariants:

- the source interaction verdict remains `not_verified` until a separate
  post-apply verification gate produces new evidence;
- human/operator approval can authorize an action path, but cannot by itself
  rewrite a failed world result into `verified`;
- every gate emits a structured envelope with `schema`, `verdict`, `reason`,
  `authority_granted`, `evidence`, and `next_allowed_gate`;
- blocked gates must be first-class results, not exceptions that callers can
  ignore;
- every mutating step requires a fresh evidence chain from the previous gate;
- read-only gates must not write store, memory, #94 rows, or live runtime
  state;
- mutating gates must be idempotent or carry a replay guard;
- every authority token must be scoped to `world_id`, `branch_id`,
  `patch_id`, `request_id`, and an expiry or generation marker.

## 2. Gate G1: Live Runtime Lookup

Purpose: read current runtime state before any submission or application.

Input:

- accepted runtime executor design request;
- target runtime descriptor copied from the apply request;
- expected source patch and citations.

Allowed behavior:

- query the live runtime read-only;
- return current world/session identity;
- return entity presence, current transform/state, version/tick, selected
  presentation state, and verification ledger cursor;
- compare the lookup target with the apply request target.

Forbidden behavior:

- submit an apply request;
- mutate runtime state;
- normalize or rewrite the semantic patch;
- mark the original interaction as verified;
- write store, memory, or #94 rows.

Ready output:

```json
{
  "schema": "agent_bridge.lswr.runtime_executor.live_lookup_gate.v0",
  "verdict": "ready_for_operator_submission_review",
  "authority_granted": "read_only_lookup_completed",
  "ready_for_submission": false,
  "ready_for_patch_application": false,
  "lookup": {
    "world_id": "onsen_live_session",
    "branch_id": "main",
    "runtime_generation": "runtime_gen_1284",
    "target_entities_present": true,
    "patch_target_still_valid": true
  }
}
```

The output is evidence for operator submission review only. It is not an
authorization to submit or apply.

## 3. Gate G2: Operator Submission

Purpose: make human/operator authorization explicit before a request can enter
the executor queue.

Input:

- ready live runtime lookup gate output;
- original design request;
- operator identity and approval intent;
- requested authority scope.

Allowed behavior:

- produce a submission token scoped to the patch, world, branch, runtime
  generation, and operator;
- set expiration and replay guard fields;
- record whether the operator approved, rejected, or requested revision.

Forbidden behavior:

- apply the patch;
- query additional live runtime state without returning to G1;
- treat UI acknowledgement as verification;
- grant broader scope than the design request and lookup evidence support.

Required token fields:

```json
{
  "submission_token": {
    "token_id": "submit_patch_arrival_bath_move_002",
    "operator_id": "human:owner",
    "world_id": "onsen_live_session",
    "branch_id": "main",
    "runtime_generation": "runtime_gen_1284",
    "patch_id": "patch_arrival_bath_move_002",
    "request_id": "apply_request_arrival_bath_move_002",
    "expires_at": "2026-06-16T23:59:59Z",
    "idempotency_key": "patch_arrival_bath_move_002/runtime_gen_1284"
  }
}
```

## 4. Gate G3: Patch Application

Purpose: perform the first mutating action, and only after G1 and G2 evidence
are both present and fresh.

Input:

- ready operator submission token;
- live lookup evidence for the same `runtime_generation`;
- original patch payload;
- rollback or compensation plan;
- executor identity.

Allowed behavior:

- lock the target runtime scope;
- apply the patch once;
- emit `runtime.patch_attempted` and `runtime.patch_result`;
- return applied, blocked, conflict, stale-runtime, or rollback-required
  status;
- attach before/after semantic state references.

Forbidden behavior:

- apply if lookup evidence is stale;
- apply if token scope does not exactly match patch/world/branch/generation;
- silently repair, expand, or reinterpret the patch;
- ingest outcome as final verification;
- rewrite the source interaction verdict.

Ready/applied output must still separate mutation from verification:

```json
{
  "schema": "agent_bridge.lswr.runtime_executor.patch_application_gate.v0",
  "verdict": "patch_applied_pending_verification",
  "mutation_performed": true,
  "verification_performed": false,
  "outcome_ingestion_allowed": false,
  "runtime_events": [
    "runtime.patch_attempted",
    "runtime.patch_result"
  ]
}
```

## 5. Gate G4: Post-Apply Verification

Purpose: decide whether the applied patch produced the expected semantic and
human-visible result.

Input:

- patch application result;
- expected effects from the semantic patch;
- fresh runtime state after application;
- presentation/visibility evidence;
- contradiction checks, when available.

Allowed behavior:

- compare expected effects against semantic state;
- compare human-visible presentation evidence against expected visibility;
- produce `verified`, `not_verified`, `inconclusive`, or `contradicted`;
- recommend rollback or revision;
- preserve both success and failure evidence.

Forbidden behavior:

- use operator approval alone as verification;
- discard failed visibility evidence;
- convert `not_verified` into `verified` without post-apply evidence;
- ingest final outcomes into memory/#94/store directly.

The verification gate owns the first point where the old failed verdict may be
superseded by new evidence:

```json
{
  "schema": "agent_bridge.lswr.runtime_executor.post_apply_verification_gate.v0",
  "verdict": "verified",
  "source_world_verdict": "not_verified",
  "supersedes_source_verdict": true,
  "evidence": {
    "semantic_effects_passed": true,
    "presentation_visible": true,
    "contradictions": []
  }
}
```

## 6. Gate G5: Outcome Ingestion

Purpose: persist the final outcome after verification, without laundering a
failed or inconclusive result.

Input:

- post-apply verification result;
- application event refs;
- operator decision refs;
- original interaction feedback refs;
- ingestion policy for the destination surface.

Allowed behavior:

- write a verified, failed, inconclusive, or contradicted outcome packet;
- attach the full chain of request, lookup, submission, application, and
  verification evidence;
- route to a specific destination such as #94 only when that destination has a
  separate accepted ingestion contract.

Forbidden behavior:

- ingest a successful outcome when verification is not successful;
- omit failed evidence;
- collapse operator approval and runtime verification into one record;
- write memory/store/#94 rows from earlier gates.

Outcome ingestion should be the only gate allowed to create durable learning or
coordination records from the execution result.

## 7. State Machine

Recommended state progression:

| State | Entered By | May Advance To | Must Not Do |
|---|---|---|---|
| `design_ready` | accepted design preflight | `lookup_ready` | query/mutate runtime |
| `lookup_ready` | G1 lookup | `submission_ready` | submit/apply |
| `submission_ready` | G2 operator token | `application_attempted` | verify/ingest |
| `application_attempted` | G3 executor | `post_apply_verified`, `post_apply_not_verified`, `rollback_required` | ingest success |
| `post_apply_verified` | G4 verification | `outcome_ingested` | hide evidence chain |
| `post_apply_not_verified` | G4 verification | `revision_required`, `rollback_required`, `outcome_ingested_as_failure` | mark verified |
| `outcome_ingested` | G5 ingestion | terminal | mutate again without new cycle |

Every transition should be replayable from structured envelopes. Screenshots or
visual captures can be attached as evidence, but the state transition should be
driven by semantic runtime data when available.

## 8. Implementation Order

Recommended narrow slices:

1. Accept this authority-gate design.
2. Implement a read-only G1 live runtime lookup preflight with fixtures and
   blocked-path tests.
3. Add G2 operator submission token design and tests, still without patch
   application.
4. Add G3 patch application as a separate executor surface with dry-run,
   idempotency, lock, and rollback evidence.
5. Add G4 post-apply verification with expected-effect checks and presentation
   evidence.
6. Add G5 outcome ingestion only after the destination contract is accepted.

The first implementation slice should stop at G1. It should prove that live
runtime lookup can be read and compared without mutating or submitting
anything.

## 9. Non-Goals

This document does not approve:

- MCP registration or profile exposure;
- a live runtime lookup implementation;
- apply-request submission;
- patch application;
- Onsen mutation;
- post-apply verification execution;
- outcome ingestion;
- store or memory writes;
- #94 ingestion;
- verification verdict rewrite;
- a general-purpose autonomous executor.

## 10. Acceptance Criteria For This Design

This design can be accepted when review confirms:

- each authority gate is independent and cannot imply later authority;
- the first mutating authority appears only at G3;
- verdict rewrite is possible only after G4 verification evidence;
- ingestion is isolated to G5 and can record failures as failures;
- implementation order starts with read-only G1 lookup, not application.
