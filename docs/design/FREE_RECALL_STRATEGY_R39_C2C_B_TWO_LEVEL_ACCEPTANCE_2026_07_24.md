# R39 — C2C-B Two-Level Acceptance Contract

Status: **ACCEPTED DESIGN DECISION**

## Decision

C2C-B reports two independent outcomes:

1. **Core curate:** accepted only when `session_curate` returns a valid core
   response with `saved_count > 0`.
2. **Observation sidecar:** finalized only when its persisted episode contains
   one `open`, contiguous `item` events, and a matching `close`. An empty,
   partial, timed-out, or failed sidecar is **Incomplete**, never finalized and
   never projected into retrieval or training material.

## Rationale

The existing schema intentionally models only `open/item/close`; adding a new
`aborted` event would require a schema migration and projection-contract change.
That is a separate storage evolution, not a prerequisite for correct C2C-B
fail-closed behavior. The existing absence/incompleteness semantics already
preserve safety: no sidecar observation is promoted without a finalized chain.

## Current acceptance

R38 establishes core-path acceptance. Its empty receipt is recorded as
sidecar-incomplete, not a failure of core curation and not an observation
success. No further live retry is required for this decision.

## Deferred work

If operators later need durable diagnostics for aborted sidecars, open a new
schema-versioned proposal with migration, projection, retention, and privacy
gates. It is not part of the current C2C-B acceptance.
