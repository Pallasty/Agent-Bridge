# Free Recall Strategy R33 — C2C-B Item Subphase Instrumentation

Date: 2026-07-24

Status: **SOURCE-ONLY / NO LIVE RUN AUTHORIZED**

Parent: R32 proves the stall occurs inside the sidecar item callback, after
core memory persistence and before callback completion.

## Objective

Split that callback into fixed redacted checkpoints around exactly two actions:

```text
item_derivation_enter / item_derivation_done
item_append_enter / item_append_done
```

The first pair bounds synchronous active-Keychain item-reference derivation;
the second bounds only the subsequent episode-item append. No value derived by
either action is written to the checkpoint channel.

## Constraints

- The writer remains compiled only under the existing default-off live-lab
  feature and writes only to the driver's already-created temporary file.
- Normal/default builds do not compile or invoke the marker.
- No Keychain enumeration, new account, database, MCP, deployment, or live
  execution belongs to R33.
- A future live probe requires a separate preregistration and one-run limit.

## Acceptance gate

The extended R27 static/mutation gate must prove the four labels are accepted
by the bridge whitelist and emitted only on either side of the two named
operations. Default-disabled compilation and the lab-feature build/tests must
pass.
