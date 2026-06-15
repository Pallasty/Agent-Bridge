# Live Semantic World Runtime - Step E4d Writer Preflight

**2026-06-15 - role: pre-implementation gate**

Parent documents:

- [Step E Outcome Ingestion Policy](LIVE_SEMANTIC_WORLD_RUNTIME_STEP_E_OUTCOME_INGESTION_2026_06_08.md)
- [Step E4 Manual Opt-In Write Design](LIVE_SEMANTIC_WORLD_RUNTIME_STEP_E4_MANUAL_OPT_IN_WRITE_DESIGN_2026_06_15.md)

Board anchors:

- `#102`: LSWR Phase 0 coordination.
- `#94`: verified-outcome stream and `present_outcome` memory row policy.

## 0. Status

This document is a preflight gate, not an implementation.

No Step E4d writer exists in this slice. E4d must remain closed until this
checklist is reviewed and an owner approval post explicitly authorizes the next
implementation slice.

## 1. Safety Objective

E4d is the first slice that could eventually persist LSWR-derived
`present_outcome` rows. The writer is therefore not a convenience tool. It is a
rare, reviewed, bounded materialization step over an already-reviewed E4c plan.

The writer must prove:

- the operator reviewed the exact candidate set being written;
- no failed or ambiguous world claim is laundered into training evidence;
- no active row is overwritten in the first write slice;
- every failure mode stops before store mutation;
- rollback evidence is emitted for every successful write.

## 2. Inherited Guardrails

E4d inherits all earlier Step E boundaries:

- E2 remains the classifier for `training_eligible`, `audit_only`, and
  `rejected`.
- E3 remains the pure dry-run candidate builder.
- E4c remains the review packet and `plan_hash` source.
- `audit_only`, `rejected`, `not_verified`, token-mismatched, and unbuildable
  records must never be write-selected.
- Human approval can authorize recording a decision, but cannot change a failed
  world verdict into `verified`.
- The writer must not call `present_outcomes_ingest(dry_run=false)`.
- The writer must not run from hooks, startup, session end, precompact, or
  automatic lifecycle paths.
- The writer must not create memory graph edges.
- The writer must stay absent from Codex-essential and standard profiles.

## 3. Future Writer Surface

Future tool name:

```text
lswr_outcome_admissions_ingest
```

Required write-mode inputs:

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

The first implementation should also accept the normal E2/E3 scan controls
(`window_secs`, `limit`, `max_candidates`) so it can recompute the plan. It must
not accept raw candidate rows from the caller.

## 4. Store Touch Order

The writer must use this exact order:

1. Parse and clamp scan controls.
2. Recompute E2 projection from persisted Step D artifacts.
3. Recompute E3 dry-run candidates.
4. Recompute E4c approval packet and `plan_hash`.
5. Validate request shape, confirmation token, approval anchors, plan hash,
   candidate keys, and caps.
6. Probe selected keys for active existing rows using a non-mutating read.
7. Fail closed if any selected key already has an active row.
8. Build `MemoryRecord`s via `crate::present_ingest::build_outcome_memory`.
9. Only after all preflight checks pass, call `memory_save` for selected rows.
10. Emit rollback packet and written key list.

Any failure before step 9 must report `writes_state=false`.

## 5. Pure Validation Function

Before adding the MCP writer, implement a pure validator with no store access:

```rust
validate_lswr_e4d_write_request(plan, request) -> validation_result
```

Minimum validation responsibilities:

- require `dry_run=false`;
- require exact `apply_confirmation`;
- require `approval_thread_id == 102`;
- require positive `approval_post_id`;
- require `reviewed_plan_hash == plan.plan_hash`;
- require non-empty `candidate_keys`;
- require every candidate key to be present in the plan;
- require `candidate_keys.len() <= max_writes`;
- require first-slice `max_writes <= 1`;
- require every selected row to have `active_row_exists == false`;
- require every selected row to have `write_allowed == false` in the plan
  until the writer explicitly flips the execution result after validation.

## 6. Failure-Mode Matrix

| Case | Required outcome |
| --- | --- |
| Missing confirmation token | error before store access; `writes_state=false` |
| Wrong confirmation token | error before store access; `writes_state=false` |
| Missing approval post id | error before store access; `writes_state=false` |
| Wrong approval thread id | error before store access; `writes_state=false` |
| Missing reviewed plan hash | error before store access; `writes_state=false` |
| Mismatched plan hash | error before store access; `writes_state=false` |
| Empty `candidate_keys` | error before store access; `writes_state=false` |
| Unknown candidate key | error before store access; `writes_state=false` |
| Candidate count above `max_writes` | error before store access; `writes_state=false` |
| First slice `max_writes > 1` | error before store access; `writes_state=false` |
| Active row already exists | error before store write; `writes_state=false` |
| Candidate became unbuildable | error before store write; `writes_state=false` |
| Store unavailable | error before mutation; `writes_state=false` |
| `audit_only` or `rejected` source | not selectable because absent from E3/E4c plan |
| `not_verified` source | not selectable because absent from E3/E4c plan |
| Token mismatch | not selectable because absent from E3/E4c plan |
| Successful first write | exactly one `present_outcome` row, rollback packet emitted |

## 7. Required Tests Before Writer Merge

The writer implementation must include tests for:

1. pure validator accepts only the exact approved request shape;
2. every failure-mode matrix row that can be unit-tested without a store;
3. store-unavailable path returns `writes_state=false`;
4. active-row collision refuses the row before `memory_save`;
5. unknown candidate key refuses before store access;
6. hash mismatch refuses before store access;
7. `audit_only`, `rejected`, `not_verified`, and token-mismatched fixtures never
   reach selected rows;
8. first successful write in a temporary store writes exactly one
   `present_outcome` row;
9. written row key, kind, scope, tags, `related_keys=[]`, and content match
   `build_outcome_memory`;
10. rollback packet includes approval post id, plan hash, written keys, and
    instruction text;
11. tool schema exposes `dry_run`, `apply_confirmation`, `approval_thread_id`,
    `approval_post_id`, `reviewed_plan_hash`, `candidate_keys`, and `max_writes`;
12. tool remains all-profile only and absent from standard and Codex-essential.

## 8. Runtime Acceptance

Before deployment, run:

```bash
cargo test -p ab-bridge lswr_outcome_admission -- --nocapture
cargo test -p ab-bridge lswr_outcome_admissions_ingest -- --nocapture
cargo check -p ab-bridge --all-targets
scripts/lswr_e4_approval_packet_smoke.sh
```

After deployment, use fresh MCP stdio probes:

- all-profile `tools/list` includes `lswr_outcome_admissions_ingest`;
- standard `tools/list` does not include it;
- Codex-essential `tools/list` does not include it;
- invalid write attempts return `writes_state=false`;
- a valid write trial must use a temporary or deliberately selected store and
  `max_writes=1`.

## 9. First Write Trial Evidence

The first valid write trial must post to `#102`:

- approval post id;
- reviewed plan hash;
- selected candidate key;
- runtime command or MCP call shape;
- written key;
- rollback packet;
- post-write memory evidence;
- confirmation that no graph edges were created by the writer.

If any expected field is missing, do not proceed to production-like writes.

## 10. Owner Approval Template

Use this shape for the owner approval post:

```text
APPROVE E4d FIRST WRITE TRIAL

approval_thread_id: 102
approval_post_id: <this post id>
reviewed_plan_hash: sha256:<hash>
candidate_keys:
- outcome_<artifact_id>
max_writes: 1
rollback_understood: yes
scope: one selected LSWR training_eligible present_outcome row
```

Approval of this template authorizes only the named first-write trial. It does
not authorize automatic ingestion, batch ingestion, active-row refreshes, graph
edges, or Codex-essential exposure.

## 11. Recommended Next Slice

Do not implement the writer directly.

Recommended next coding slice:

1. add the pure request validator and tests;
2. add a read-only validation preview that consumes the live E4c plan and a
   proposed request object but still writes nothing;
3. ask for owner review again before adding the actual `memory_save` path.
