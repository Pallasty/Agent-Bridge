# SEPL P1A5 Persisted AGENT.md Proposal Artifact

## Scope

P1A5 adds a source-only proposal artifact that retains the exact candidate
body in SQLite and detects inconsistent persistence with a domain-separated
record hash. Creation and readback are inherent
`SqliteStore` methods only. There is no `StateStore`, MCP, CLI, scheduler,
bootstrap, producer, approval, or apply surface.

## Trust Boundary

`persistence_integrity_verified=true` means the loaded fields reproduce the
record hash and satisfy the P1A3 receipt and candidate invariants. Because the
hash is public and the SQLite file is writable by local processes, it cannot
authenticate where the row came from. `source_authenticity_verified`,
`eligible_for_human_review`, and `automatic_apply_allowed` therefore remain
false. The `producer_id` is untrusted attribution metadata, not a signature.

## Artifact

The record binds:

- content-addressed proposal id and record hash;
- resource id and caller-supplied producer id;
- caller-supplied proposal timestamp;
- exact observed-current and candidate bytes;
- the complete P1A3 receipt, including binding and lineage-head evidence.

The record hash uses the
`agent-bridge/sepl/resource-persisted-proposal/v0` domain and length-frames every
field. Identical inputs are idempotent. Readback recomputes the record hash
and candidate hash and fails closed on corruption or tampering.

## Workflow

1. Reuse P1A3 to validate the current opened `AGENT.md`, binding, complete
   lineage, optional expected hash, optional historical target, and candidate.
2. Serialize the validated receipt and compute the proposal record hash over
   the receipt plus exact current/candidate bytes and attribution fields.
3. Insert the content-addressed record with `INSERT OR IGNORE` using the record hash as
   proposal id.
4. Read the record back and recompute hashes, byte/line counts, diff summary,
   and no-mutation claims before returning it.

P1A5 makes the candidate available to a later authenticity and human-review
protocol, but does not itself admit that review or perform semantic review.

## Non-Claims

P1A5 does not cryptographically identify an external producer, prove current
filesystem state after creation, approve policy meaning, reserve a lease,
exclude external writers, modify `AGENT.md`, append lineage, or authorize
automatic application.

## Test Floor

- persist and reopen the exact candidate with verified record integrity;
- identical artifacts are content-addressed and idempotent;
- persisted candidate tampering fails record-hash verification;
- file content and resource lineage remain unchanged;
- existing P0 through P1A4 tests remain green.
