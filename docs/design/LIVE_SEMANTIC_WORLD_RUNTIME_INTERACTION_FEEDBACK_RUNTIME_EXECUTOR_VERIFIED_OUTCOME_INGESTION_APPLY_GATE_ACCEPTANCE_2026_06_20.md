# G21 Verified Outcome Ingestion Apply Gate Acceptance

Status: PROPOSED

Date: 2026-06-20

## Verification

```bash
cargo test -p ab-bridge --test lswr_interaction_feedback_fixture interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate -- --nocapture
bash -n scripts/verify-biocortex-retrieval-shadow.sh
git diff --check
```

## Expected Signals

- missing apply decision blocks with
  `explicit_verified_outcome_ingestion_apply_decision_required`;
- explicit apply decision emits
  `verified_outcome_ingestion_apply_verdict=ready_for_verified_outcome_ingestion_writer`;
- `next_allowed_gate=verified_outcome_ingestion_writer`;
- `ready_for_verified_outcome_ingestion_writer=true`;
- source scope must match the G20 commit package;
- bad decisions reject wrong decision kind, wrong approval, unconfirmed
  packages, writer-boundary gaps, unsafe write flags, and scope mismatches;
- the gate remains output-only:
  `writes_state=false`, `store_access_required=false`,
  `mcp_tool_registered=false`,
  `verified_outcome_ingested_by_this_tool=false`, and
  `world_verdict_persisted_by_this_tool=false`.

