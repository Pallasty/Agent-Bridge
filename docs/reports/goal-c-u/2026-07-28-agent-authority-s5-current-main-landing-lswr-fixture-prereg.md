# S5 current-main landing LSWR fixture reconciliation preregistration

Date: 2026-07-28

Status: **FROZEN_BEFORE_FIXTURE_UPDATE**

Runtime authority: **NONE**

## Blocking observation

The locked offline `ab-bridge --all-targets --no-default-features` test
reached one deterministic failure after the S1 landing hardening passed:

```text
lswr_readonly_bridge_consumer::
consumer_summary_fixture_matches_generated_detailed_summary
```

Only the snapshot digest differed:

```text
generated: sha256:9ab9297aa85d3ac5e0db9e21d98f20e134a94991819d48ca1a1880a6d421137e
fixture:   sha256:5ff171f505327b9d93f01a1dfc44a6159a00f48e6085a5e7a63e5eded6629495
```

The same focused failure was reproduced on the untouched S5 result
`dc90f19fc83df7181708c4e05c2af35dd0b6e4ec`. The relevant test, input
fixture, expected fixture, and builder source have identical Git blobs on
current master `0b95c231b4ac61743c297b45b0abf81690bd3fd6` and S5.

## Root-cause boundary

Both current typed input paths produce the new digest:

- round-tripping
  `crates/bridge/tests/fixtures/lswr_ledger_snapshot_v0.json`;
- the independent hardcoded snapshot in
  `lswr_readonly_bridge_projection`.

The ledger round-trip has no structural, scalar, collection-length, or JSON
key-order difference from its input. Counts remain `1 action / 2 events /
1 verification / 1 feedback / 1 rollback record`. The read-only affordances
remain `snapshot=true`, `query=true`, and `patch/action/invoke=false`.

The stale digest appears only in these seven derived fixtures:

1. `lswr_readonly_bridge_projection_v0.json`;
2. `lswr_readonly_bridge_consumer_summary_v0.json`;
3. `lswr_readonly_bridge_report_detailed_v0.md`;
4. `lswr_readonly_bridge_report_counts_only_v0.md`;
5. `lswr_readonly_bridge_report_packet_v0.json`;
6. `lswr_readonly_bridge_acceptance_matrix_v0.json`; and
7. `lswr_readonly_bridge_display_model_v0.json`.

## Planned reconciliation

Generate the five JSON artifacts with the existing typed examples in
dependency order:

1. projection from the independent hardcoded snapshot;
2. consumer summary from the ledger snapshot;
3. report packet from the ledger snapshot;
4. acceptance matrix from the newly generated packet; and
5. display model from the newly generated packet.

Generate the detailed Markdown report with the existing report example.
Update the counts-only report's digest line and require its existing renderer
test to prove exact output.

Before replacing fixtures, parse old and generated JSON and normalize only the
old digest to the new digest. The normalized values must compare equal. The
detailed report must likewise differ only in its digest line. Any other
semantic difference stops this reconciliation.

## Verification

- exact generated digest from both independent snapshot inputs;
- JSON parse and normalized semantic equality;
- focused projection, consumer, report, packet, acceptance, and display tests;
- scan proving the stale digest is absent from the LSWR fixture lane;
- locked offline `ab-bridge --all-targets --no-default-features` check;
- locked offline `ab-bridge --all-targets --no-default-features` test;
- formatting, diff, secret/private-key, and runtime/public-surface scans.

## Boundary

This is a deterministic test-fixture reconciliation in a separate commit on
the isolated landing branch. It does not change LSWR source behavior, register
an MCP tool, expose a mutation surface, access live state, update master,
deploy, enable runtime/shadow/executor behavior, or grant production authority.
