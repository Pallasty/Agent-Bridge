# SEPL P1A6 Proposal Review Observation

## Scope

P1A6 persists a content-addressed observation that a caller reported reviewing
one P1A5 `AGENT.md` proposal artifact. Creation and readback remain inherent
`SqliteStore` methods. There is no `StateStore`, MCP, CLI, scheduler, producer,
apply, or runtime-policy surface.

## Trust Boundary

The record binds a verified P1A5 proposal record hash to a caller-supplied
reviewer label, timestamp, disposition, and reason. The allowed dispositions
are `accept_candidate`, `reject_candidate`, and `defer`.

These values record an observation, not authority. The reviewer label is not a
signature or authenticated identity. Therefore every artifact keeps:

- `reviewer_identity_authenticated=false`;
- `human_review_authenticated=false`;
- `source_authenticity_verified=false`;
- `semantic_review_authority_granted=false`;
- `automatic_apply_allowed=false`.

`human_review_claimed=true` means only that the caller supplied a review
observation. It is not proof that a human performed the review.

## Integrity Model

The review id is the SHA-256 record hash over length-framed fields under the
`agent-bridge/sepl/resource-proposal-review-observation/v0` domain. Creation
first performs full P1A5 readback validation. Readback recomputes the review
hash, reloads the referenced P1A5 artifact, and requires the proposal record
hash to remain identical.

Identical observations are idempotent through `INSERT OR IGNORE`. Different
review observations can coexist for the same proposal; P1A6 does not choose a
winner, collapse history, or interpret an acceptance claim as approval.

## Non-Claims

P1A6 does not authenticate a reviewer or producer, establish quorum, resolve
conflicting observations, grant semantic authority, mark a proposal eligible
for application, mutate `AGENT.md`, append resource lineage, reserve a lease,
or authorize automatic execution.

## Test Floor

- fresh and concurrent migration are additive and idempotent;
- incompatible or partial review schema fails closed and rolls back;
- valid observations persist and reopen with both review and proposal hashes
  verified;
- identical observations are content-addressed and idempotent;
- review-row or referenced-proposal tampering fails readback;
- invalid disposition, identity, timestamp, and reason are rejected;
- proposal bytes, `AGENT.md`, and resource lineage remain unchanged.

