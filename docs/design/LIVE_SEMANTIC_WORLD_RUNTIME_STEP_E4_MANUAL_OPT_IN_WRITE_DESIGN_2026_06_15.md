# Live Semantic World Runtime - Step E4 Manual Opt-In Write Design

**2026-06-15 - role: owner-approval design package**

Parent policy:

- [Step E Outcome Ingestion Policy](LIVE_SEMANTIC_WORLD_RUNTIME_STEP_E_OUTCOME_INGESTION_2026_06_08.md)
- [Step E4d Writer Preflight](LIVE_SEMANTIC_WORLD_RUNTIME_STEP_E4D_WRITER_PREFLIGHT_2026_06_15.md)

Board anchors:

- `#102`: LSWR Phase 0 coordination.
- `#94`: verified-outcome stream and `present_outcome` memory row policy.
- `#6`: memory graph substrate and `present_outcome` graph-coverage exclusion.

## 0. Status

This document is a design package only.

No E4 write path is implemented by this document. E0-E3 are already implemented
and deployed; E4 remains closed until owner approval is recorded after reviewing
this design.

## 1. Purpose

E3 proves that a `training_eligible` LSWR admission can be transformed into a
#94-compatible `present_outcome` memory candidate without writing state.

E4 defines the conditions under which a future operator may persist those
candidates as ordinary memory rows.

The goal is not to make ingestion convenient. The goal is to make a rare write
safe, reviewable, bounded, reversible, and impossible to trigger accidentally.

## 2. Non-Goals

E4 must not:

- enable automatic LSWR memory writes;
- run from hooks, session finalization, precompact, or startup;
- expose any LSWR write tool in Codex essential or standard profiles;
- call `present_outcomes_ingest(dry_run=false)` directly;
- ingest `audit_only`, `rejected`, `not_verified`, or token-mismatched records;
- turn human approval into proof of a failed world claim;
- create memory graph edges;
- change `present_outcome` scope/tag semantics;
- overwrite existing active `present_outcome` rows in the first write slice.

## 3. Proposed Future Surface

Future tool name:

```text
lswr_outcome_admissions_ingest
```

Profile:

- `AGENT_BRIDGE_TOOL_PROFILE=all`: visible.
- `AGENT_BRIDGE_TOOL_PROFILE=standard`: hidden.
- `AGENT_BRIDGE_TOOLSET=codex-essential`: hidden.

Default mode:

```json
{
  "dry_run": true
}
```

Write mode must require all of:

```json
{
  "dry_run": false,
  "apply_confirmation": "persist_lswr_training_eligible_outcomes",
  "approval_thread_id": 102,
  "approval_post_id": 0,
  "reviewed_plan_hash": "sha256:...",
  "candidate_keys": ["outcome_<artifact_id>"],
  "max_writes": 1
}
```

`approval_post_id` is intentionally part of the contract. The implementation
does not need to trust forum contents, but the operator must provide a durable
coordination anchor before a write can happen.

## 4. Dry-Run-First Contract

The write path must be a consumer of the E3 candidate builder. It must not
reimplement LSWR admission gates.

Dry-run response shape:

```json
{
  "schema": "agent_bridge.lswr.outcome_admission_ingest_plan.v0",
  "dry_run": true,
  "writes_state": false,
  "plan_hash": "sha256:<canonical candidate rows>",
  "candidate_count": 1,
  "max_writes": 1,
  "rows": [
    {
      "key": "outcome_<artifact_id>",
      "kind": "present_outcome",
      "scope": "outcome:<artifact_id>",
      "active_row_exists": false,
      "write_allowed": false,
      "requires_review": true
    }
  ]
}
```

Write mode must recompute the plan and fail closed unless:

1. `reviewed_plan_hash` equals the current dry-run `plan_hash`;
2. every `candidate_keys[]` value is present in the current plan;
3. `candidate_keys.len() <= max_writes`;
4. `max_writes` is small; recommended first limit is `1`;
5. no selected row has `active_row_exists=true`;
6. the selected rows still originate from `training_eligible` admissions.

The plan hash is load-bearing. It prevents a human from reviewing one candidate
set and accidentally writing a later, larger, or different set.

## 5. Write Semantics

If E4 is approved later, the first implementation should write exactly the
`MemoryRecord` constructed by the existing #94 helper:

```rust
crate::present_ingest::build_outcome_memory(...)
```

The resulting row remains ordinary memory:

- `key = outcome_<artifact_id>`;
- `kind = present_outcome`;
- `scope = outcome:<artifact_id>`;
- tags include `present_outcome`, `verified_outcome`, `auto_ingested`, and
  verification/method/decision/embody tags when present;
- `related_keys = []`;
- `importance = 0.5`.

The first E4 write implementation should reject active-row refreshes. That keeps
rollback simple: a first write either creates a new deterministic row or does
nothing. Refresh/overwrite can be designed later as a separate owner-approved
slice.

## 6. Rollback Packet

Every successful write response must include a rollback packet:

```json
{
  "schema": "agent_bridge.lswr.outcome_admission_ingest_rollback.v0",
  "approval_post_id": 0,
  "plan_hash": "sha256:...",
  "written_keys": ["outcome_<artifact_id>"],
  "rollback_instruction": "tombstone these exact keys through the existing memory admin path"
}
```

The rollback packet is evidence and operator guidance, not an automatic undo
button. Automatic rollback would be another write path and should not be added
to the initial E4 implementation.

## 7. Failure Modes

The write tool must return structured failures before touching the store for:

- missing or wrong `apply_confirmation`;
- missing `approval_post_id`;
- missing `reviewed_plan_hash`;
- plan hash mismatch;
- `candidate_keys` empty or not a subset of the plan;
- selected candidate count above `max_writes`;
- active row already exists;
- no store configured;
- all selected candidates became unbuildable after reclassification.

The response must say `writes_state=false` on every preflight failure.

## 8. Acceptance Tests For Future Implementation

Required tests before any E4 code merges:

1. `dry_run=true` returns a plan hash and writes nothing.
2. `dry_run=false` without `apply_confirmation` fails before store access.
3. `dry_run=false` without `approval_post_id` fails before store access.
4. `dry_run=false` with mismatched `reviewed_plan_hash` fails before store access.
5. `dry_run=false` with an unknown `candidate_key` fails before store access.
6. `dry_run=false` with `active_row_exists=true` refuses the row.
7. `audit_only` and `rejected` admissions never enter selected rows.
8. Token-mismatched records cannot be written.
9. A single selected `training_eligible` candidate writes exactly one
   `present_outcome` row with deterministic key/scope/tags and `related_keys=[]`.
10. The tool is registered under all-profile only and absent from standard and
    Codex-essential.

## 9. Suggested Implementation Slices

### E4a - Approval Packet Design

Land this document and ask for owner sign-off on #102.

### E4b - Pure Plan Hash Function

Add a pure function that canonicalizes E3 candidate rows and returns
`plan_hash`. No MCP tool and no store access yet.

### E4c - Read-Only Approval Packet Tool

Expose a read-only all-profile tool that returns the E4 dry-run plan and hash.
It must not accept `dry_run=false`.

### E4d - Explicit Write Tool

Only after owner approval of E4a-E4c, add `lswr_outcome_admissions_ingest` with
`dry_run=true` default and the write gates above.

### E4e - First Manual Write Trial

Run with `max_writes=1` against a known non-production or deliberately selected
candidate. Record the approval post, plan hash, written key, rollback packet, and
post-write `memory_search` evidence on #102.

## 10. Recommended Decision

Do not implement E4 write code yet.

Recommended next action is owner review of this document. If accepted, the next
coding slice should be E4b/E4c only: pure plan hash plus read-only approval
packet. The actual `dry_run=false` writer should remain a later, separately
approved slice.

## 11. E4b/E4c/E4d Read-Only Implementation Status

Implemented after owner go-ahead in the Codex lane:

- pure plan-hash support in `lswr_outcome_admission`;
- all-profile-only read-only tool `lswr_outcome_admissions_approval_packet`;
- response schema `agent_bridge.lswr.outcome_admission_ingest_plan.v0`;
- stable `sha256:` plan hash over canonical candidate rows sorted by memory key;
- optional active-row status via non-mutating `memory_search` probes;
- `dry_run=true`, `writes_state=false`, and `write_tool_open=false` in the
  returned packet.

E4d read-only preflight has also been added:

- pure validator `validate_lswr_e4d_write_request(plan, request)`;
- all-profile-only read-only tool `lswr_outcome_admissions_write_preflight`;
- response schema `agent_bridge.lswr.outcome_admission_write_preflight.v0`;
- validates a proposed future writer request against the recomputed E4c plan;
- rejects missing/wrong confirmation, approval anchor, reviewed plan hash,
  candidate keys, write caps, duplicate/unknown keys, active rows, and unknown
  active-row status;
- still returns `dry_run=true`, `writes_state=false`, `store_access_required=false`,
  and `write_tool_open=false`.

Repeatable non-empty smoke:

```bash
scripts/lswr_e4_approval_packet_smoke.sh
```

This local smoke reuses the Step E3 fixture generator, then asserts the E4c
approval packet has a non-empty candidate set, `dry_run=true`,
`writes_state=false`, `write_tool_open=false`, a `sha256:` plan hash, and no
active rows. It does not call MCP and does not write memory.

Still not implemented:

- no `lswr_outcome_admissions_ingest` writer;
- no `dry_run=false` surface;
- no top-level executable `max_writes` input outside the read-only proposed
  request object;
- no `present_outcomes_ingest(dry_run=false)` call;
- no Codex-essential or standard profile exposure.

The next owner-gated step remains E4d: explicit writer design/implementation
with confirmation token, approval post id, reviewed plan hash, candidate keys,
and first-run cap.

Before implementing the writer, follow the
[Step E4d Writer Preflight](LIVE_SEMANTIC_WORLD_RUNTIME_STEP_E4D_WRITER_PREFLIGHT_2026_06_15.md).
The recommended next coding slice after this preflight is owner review, then a
separately approved first-write implementation trial, not automatic
`memory_save`.
