# Acceptance — Runtime Executor World Verdict Rewrite Gate

Date: 2026-06-20

Status: Draft acceptance notes

## 1. Required Checks

Focused fixture:

```text
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_world_verdict_rewrite_gate -- --nocapture
```

Expected:

- missing rewrite decision blocks with
  `explicit_world_verdict_rewrite_decision_required`;
- explicit scoped rewrite decision returns
  `ready_for_verified_outcome_ingestion_gate`;
- bad rewrite decision blocks on kind, decision, source verdict, target
  verdict, claim, attestation, lineage, digest, idempotency, permission, and
  scope errors;
- wrong source input blocks with
  `runtime_executor_durable_outcome_record_write_evidence_review_preflight_required`.

Blocked smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_world_verdict_rewrite_gate_smoke -- --format json --assert-blocked-without-world-verdict-rewrite-decision --assert-output-only
```

Ready smoke:

```text
cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_world_verdict_rewrite_gate_smoke -- --with-world-verdict-rewrite-decision --format json --assert-ready-for-verified-outcome-ingestion-gate --assert-output-only
```

Expected ready fields:

- `world_verdict_rewrite_gate_verdict=ready_for_verified_outcome_ingestion_gate`;
- `next_allowed_gate=verified_outcome_ingestion_gate`;
- `previous_world_verdict=not_verified`;
- `rewritten_world_verdict=verified`;
- `ready_for_verified_outcome_ingestion_gate=true`;
- `world_verdict_rewrite_output_only=true`;
- `world_verdict_persisted_by_this_tool=false`;
- `durable_outcome_record_written_by_this_tool=false`;
- `memory_write_allowed=false`;
- `outcome_ingestion_allowed=false`;
- `verified_outcome_ingestion_performed_by_this_tool=false`.

## 2. Boundary

This accepted G17 gate can emit a bounded `verified` verdict package from a
scoped explicit rewrite decision. It cannot persist that verdict, write a
durable outcome record, ingest #94 outcomes, write memory, or expose MCP tools.

The critical distinction is:

- `decision=rewrite_world_verdict_to_verified`: explicit decision authorizes
  the output rewrite package;
- `world_verdict_rewrite_gate_verdict=ready_for_verified_outcome_ingestion_gate`:
  the next gate may consume this package;
- `world_verdict_rewrite_output_only=true`: the rewrite remains package output,
  not durable state;
- `world_verdict_persisted_by_this_tool=false`: no persisted verdict changed
  here.

## 3. Next Slice

The next safe slice is the verified outcome ingestion gate. It must require its
own ingestion decision and must not treat a ready G17 package as already
ingested or persisted.
