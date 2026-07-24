# Free Recall Strategy R34 — C2C-B Item Subphase Probe

Date: 2026-07-24

Status: **ATTEMPT-1 INCOMPLETE / NO RETRY**

Parent: R32 located the timeout inside the item-sidecar. R33 separates the
two operations in that callback with fixed labels only.

## Objective

Run one fresh disposable probe to classify the final completed label:

- `item_derivation_enter` without `item_derivation_done`: synchronous active
  Keychain item-reference derivation is the blocker.
- `item_derivation_done` and `item_append_enter` without `item_append_done`:
  the SQLite episode-item append is the blocker.
- a later label or a finalized receipt: record it as observed; do not infer a
  retry authority.

## Fixed envelope

Use R33 commit `bce3c659` or a descendant that changes no live-lab source.
After all no-Keychain preconditions pass, execute exactly once:

```text
target/debug/episode-observation-c2c-live-lab \
  --agent-bridge "$PWD/target/debug/agent-bridge" \
  --execute-r26-live r26-c2c-live-authorized
```

It uses fresh random disposable Keychain accounts, a new temporary SQLite
database, and the driver-owned temporary checkpoint file. Existing Keychain
items are neither enumerated nor read.

## Preconditions and limits

R27 and R33 static/mutation gates, default-disabled check, R33 feature build,
driver tests, and the isolated ordinary MCP save must pass. The child is
killed/reaped before diagnostics are read and custody cleanup/postcheck must
complete. There is no retry under R34, deployment, merge, or production change.

## Attempt-1 receipt

All fixed preconditions passed, including the isolated ordinary MCP fixture
(`saved_count=1`). The one authorized disposable run returned:

```text
after_initialize_before_curate_response; last_checkpoint=item_derivation_enter
```

The sidecar entered synchronous item-reference derivation but did not complete
it before the deadline. The SQLite episode-item append was therefore not
started. The child was reaped before diagnostics were read and custody
cleanup/postcheck completed. R34 is incomplete and will not be retried.

The next lane is source-only: preserve the default-off Keychain boundary while
moving or bounding derivation so a stalled Security framework call cannot hold
the MCP request's response path indefinitely.
