# SEPL P1A4 AGENT.md Proposal Review Admission

## Scope

P1A4 adds a source-only, read-only review preflight for a P1A3
proposal receipt. It is an inherent `SqliteStore` method only. It is not
exposed through `StateStore`, MCP, CLI, scheduler, session bootstrap, or an
automatic producer.

P1A3 does not persist proposal records or return the candidate body. P1A4
therefore does not claim to list proposals or perform semantic review. It
checks receipt invariants and re-observes the current `AGENT.md` file,
binding, and complete lineage. The result is `current_unverified`, `stale`,
or `invalid` and always denies human-review admission and automatic
application.

## Protocol

1. Validate the resource id, `AGENT.md` filename, and review timestamp.
2. Validate the P1A3 schema, scope, hashes, binding/version record hashes,
   line-summary invariants, historical-target claim, and no-mutation flags.
3. Open the requested path with Unix `O_NOFOLLOW`, resolve its canonical path,
   reopen it, and require device/inode/content identity to match.
4. In a read-only SQLite transaction, re-read the opened file and compare its
   hash, byte count, and line count with the proposal receipt.
5. Require the current binding and lineage head to equal the receipt and
   validate the complete lineage.
6. Return `current_unverified` when no invariant or current-state violation
   exists. A well-formed receipt whose observed state moved is `stale`; a
   receipt with broken invariants is `invalid`.

## Non-Claims

The review does not authenticate that a receipt was emitted by P1A3, retain or
recover the candidate body, inspect semantic suitability, approve policy
content, apply a change, reserve a lease, exclude a later external writer, or
create an execution path. `source_authenticity_verified`,
`eligible_for_human_review`, and `automatic_apply_allowed` are always false.

## Test Floor

- a fresh P1A3 receipt is current but unauthenticated, without file or lineage
  mutation;
- a receipt becomes stale after the file and lineage advance;
- forged mutation claims make a receipt invalid;
- existing P0/P1A0/P1A1/P1A2/P1A3 tests remain green.
