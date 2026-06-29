# BioCortex C1 Composed Limit-Cycle Consumer Dry-Run

Date: 2026-06-29
Status: static read-only schema-v4 consumer fixture, no runtime enablement

## Summary

Agent-Bridge now has a local static consumer for the BioCortex C1
composed-limit-cycle schema-v4 ledger:

```text
agent_bridge.biocortex_composed_limit_cycle.consumer_dry_run.v0
agent_bridge.biocortex_composed_limit_cycle.review_artifact.v0
agent_bridge.biocortex_composed_limit_cycle.report_packet.v0
agent_bridge.biocortex_composed_limit_cycle.display_model.v0
```

Implementation:

- `crates/bridge/src/biocortex_composed_limit_cycle.rs`
- `crates/bridge/tests/biocortex_composed_limit_cycle.rs`
- `crates/bridge/tests/fixtures/biocortex_composed_limit_cycle_schema_v4.txt`

The consumer parses a precomputed `key=value` ledger artifact from
`biocortex-rs` and validates the C1 positive, load-bearing controls, disclosed
caveats, scope non-claims, and generic read-only hard-false fields. It does not
run BioCortex, call Agent-Bridge memory APIs, mutate graph edges, change
retrieval order, register an MCP tool, open sockets, call Nexus or AiOT, or
enable runtime/shadow execution.

## Boundary

Accepted ledgers produce:

```text
verdict=accepted
downstream_action=display_or_review_only
integration_decision=shadow_only_no_runtime_admission
```

Rejected ledgers produce:

```text
verdict=rejected
downstream_action=reject_static_ledger_artifact
integration_decision=blocked_by_static_ledger_validation
```

This is a separate C1 slice consumer. It does not mutate the frozen schema-v3
unified capability-ledger consumer.

## Negative Coverage

The fixture includes rejection coverage for:

- generic hard-false tampering: `executor_enabled=false` to
  `executor_enabled=true`;
- caveat weakening: `lif_nonlinearity_load_bearing=false` to `true`;
- caveat-basis weakening: `replay_is_threshold_linear_reproducible=true` to
  `false`;
- supplied primitive relabeling:
  `assembly_ring_plus_convergence_plus_delay` to `bare_recurrence`;
- scope escalation: `is_auto_associative_attractor=false` to `true`;
- malformed non-`key=value` input.

## Non-Claims

- This dry-run does not write AB memory or graph edges.
- This dry-run does not mutate retrieval order.
- This dry-run does not expose an MCP tool or registry entry.
- This dry-run does not run BioCortex or consume live BioCortex checkout state.
- This dry-run does not touch Nexus, AiOT, runtime, executor, or live world
  events.
- This dry-run does not claim cognition, language, agency, planning, or
  autonomous objective discovery.

## Verification

Focused checks for this slice:

```bash
CARGO_TARGET_DIR=/tmp/agent-bridge-biocortex-c1-target cargo test -p ab-bridge --test biocortex_composed_limit_cycle -- --quiet
CARGO_TARGET_DIR=/tmp/agent-bridge-biocortex-c1-target cargo test -p ab-bridge --test biocortex_capability_ledger_consumer -- --quiet
CARGO_TARGET_DIR=/tmp/agent-bridge-biocortex-c1-target cargo test -p ab-bridge --test biocortex_capability_ledger_display_packet -- --quiet
rustfmt --edition 2021 --check crates/bridge/src/biocortex_composed_limit_cycle.rs crates/bridge/tests/biocortex_composed_limit_cycle.rs
git diff --check
```
