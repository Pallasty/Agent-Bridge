# BioCortex Track B S21B-A2: unsigned-subject contract rebinding and generation review

Date: 2026-07-19

## Decision

S21B-A1 closed a non-live role-build receipt for integration
`3df8536c841390fdc593fa4a518885b3f2291fc6`.  That receipt is valid evidence
for A1 only.  It may begin this review, but it cannot be copied into a final
subject for a repository that is changed by this review.

The legacy S21A subject schema and Rust validator are deliberately treated as
stale for A1: they freeze Cargo.lock
`408e0aa5e6bc3f2a318719c57419ece60b507df0a11c1738fd40dda66aac1f59`, while
the A1 integration freezes
`726a447607f32fe6bbc05b9a75b5614cff8f0dc6561f51f0632ccc2459a7af30`.
Neither the legacy schema nor its fixture may validate an A1 or A2 subject.

## What this stage adds

- a closed synthetic review packet with a domain-separated self-hash;
- an exact A1 ordered-parent and external-receipt provenance binding;
- an explicit replacement subject schema identity and field requirements; and
- a fail-closed successor rule: after A2 integration, two new clean archive
  rebuilds are required before one external unsigned subject may be generated.

The review packet is not the replacement subject.  It is synthetic, remains in
the repository, and states that the A1 receipt is not A2 evidence.  The real
A2 receipt and any real subject must remain outside the repository.

## Required future evidence

A real replacement subject may be built only from a fresh A2 integration
receipt that independently proves the exact ordered topology, archive,
Cargo.lock, four role artifacts, and toolchain/feature/schema/recipe closures
in two clean archive roots. Candidate-provided expected hashes are never an
authority. The external subject generator must compare its candidate with an
independent reconstruction from that receipt.

## Nonclaims

This stage does not emit a real subject, signing message, owner anchor, key,
signature, authorization envelope, external-input admission, execution permit,
or live output. It unlocks no side effects and requires no owner action.
