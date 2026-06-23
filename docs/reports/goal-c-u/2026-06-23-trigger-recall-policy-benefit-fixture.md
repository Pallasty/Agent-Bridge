# Trigger Recall Policy-Benefit Fixture

Date: 2026-06-23

Scope: add a repo-local, read-only contract fixture for the future held-out
policy-benefit evaluation required before production `enforce_hold` can be
reopened.

This slice does not implement production `enforce_hold`, does not change
default `memory_search`, does not register an MCP tool, does not mutate a
memory DB, does not write graph edges, does not reindex, and does not change
runtime retrieval behavior.

## Why

The previous gates left the production line in the correct parked state:

- the portable Stage-2 fixture is a deterministic code-regression gate;
- the legacy aio2 baseline audit is stale telemetry when phantom-gold rows are
  absent;
- production `enforce_hold` remains off until a real held-out policy-benefit
  eval over a non-phantom corpus proves benefit.

The missing artifact was a reusable policy-benefit evidence shape. Without it,
the next review could again confuse code-regression proof, stale live telemetry,
and production approval.

## What Changed

`crates/bridge/examples/trigger_recall_eval.rs` now supports:

```bash
cargo run -p ab-bridge --example trigger_recall_eval -- --policy-benefit-fixture
```

The command reuses the repo-local portable Stage-2 fixture rows and emits a
machine-readable summary with schema:

```text
agent_bridge.memory.trigger_recall.policy_benefit_eval.v0
```

The summary checks the contract that a future real held-out corpus must satisfy:

| Metric | Required Direction |
|---|---|
| positive baseline hits | all positive cases must be baseline-findable |
| positive cases held | zero |
| true hits lost by shadow gate | zero |
| accepted order drift | zero |
| baseline false hits before gate | greater than zero |
| baseline false hits after gate | zero |
| false hits removed by shadow gate | greater than zero |

The fixture intentionally reports:

```text
production_evidence_authority=false
ready_for_production_review=false
production_enforce_hold_authorized=false
next_required_gate=run_same_contract_on_real_non_phantom_heldout_corpus
```

## Verification

Commands run from
`/Users/pallasting/Projects/agent-bridge-trigger-policy-benefit-eval-plan`:

```bash
rustfmt --check crates/bridge/examples/trigger_recall_eval.rs
CARGO_BUILD_JOBS=2 cargo test -p ab-bridge --example trigger_recall_eval policy_benefit -- --nocapture
CARGO_BUILD_JOBS=2 cargo run -p ab-bridge --example trigger_recall_eval -- --policy-benefit-fixture
```

Observed results:

- rustfmt check passed after formatting the example file.
- targeted `policy_benefit` tests passed: 2 passed.
- fixture command passed with existing warnings only.

Fixture output summary:

| Metric | Observed |
|---|---:|
| positive baseline hits | 3/3 |
| positive cases held | 0 |
| true hits lost by shadow gate | 0 |
| accepted order drift | 0 |
| baseline false hits before gate | 8 |
| baseline false hits after gate | 0 |
| false hits removed by shadow gate | 8 |

Held controls by reason:

| Reason | Count |
|---|---:|
| creative_non_continuation_intent | 1 |
| frontend_dashboard_intent | 1 |
| write_bypass_intent | 1 |

## Boundary

This is only a contract fixture. It is not production evidence because it is
repo-local, tiny, and synthetic. It proves that the evaluation shape can detect
the desired tradeoff:

- legitimate continuations remain visible;
- overlapping false-hit controls are removed;
- unrelated no-hit controls do not create fake benefit;
- production approval remains false.

## Next Gate

Build or select a real, non-phantom held-out corpus and run the same contract
against it. A future production review packet should require the resulting
`policy_benefit_eval.v0` summary and should still name an exact implementation
commit before any `enforce_hold` candidate is reopened.
