# S13 recovered-envelope local delivery

Date: 2026-07-15
Decision: `BLOCKED_FAIL_CLOSED`
Scope: private, default-off, synthetic preregistration

## Outcome

S13 closes two local executable gaps without claiming a runtime integration:

1. complete typed S9 request/decision values can be placed in an owned carrier
   together with their exact canonical request message, exact canonical decision
   message, and exact 64-byte Ed25519 signature;
2. an owned signed S10 query/observation can be verified into a sealed S10
   projection and handed directly to the S12 historical verifier in the same
   lexical call.

The carrier is structural input, not trusted evidence. The handoff is a
process-local Rust ownership property, not an external transport, durable
mailbox, global exactly-once guarantee, or replay fence. The result remains the
private S12 historical observation and cannot become currentness or admission.

## Boundary

```text
owned S9 structural envelope
  typed request + exact canonical request message
  typed signed decision + exact canonical decision message + exact signature
                         │
owned S10 query + signed observation
                         │ consume self
                         ▼
             pure S10 verification
                         │ sealed projection exists only in this stack frame
                         ▼
             unchanged S12 re-verifier
                         │
                         ▼
        private historical-only observation
        NOT currentness · NOT admission · NOT transport
```

There is no byte-only decoder. A future external source must define a strict
wire schema and prove that it rejects duplicate, aliased, defaulted, unknown,
truncated, and trailing fields before it can construct these typed values.

## Owned envelope

The private `RecoveredS9EnvelopeV1` is non-`Clone`, non-`Copy`,
non-serializable, has no public fields, and owns all of its input. Its
constructor checks raw lengths before typed framing or hashing:

- request message: `1..=65,536` bytes;
- decision message: `1..=65,536` bytes;
- signature: exactly 64 bytes;
- combined raw payload: at most 131,072 bytes.

It then rebuilds the S9 request and decision messages using the shared S9
validated framers and requires byte-for-byte equality. The separately carried
signature must exactly equal the signature in the typed decision. This matters
because the canonical S9 decision message is the signed message and does not
itself contain the signature.

The envelope digest is domain-separated under:

```text
agent-bridge/track-b/recovered-envelope-delivery/envelope-digest/v1
```

It binds the S13 policy/profile, envelope schema, S9/S10/S11/S12 contract
identities, exact canonical request message, exact canonical decision message,
and exact signature. It is a structural commitment only, not authentication or
provenance.

## Consuming handoff

The private handoff owns the envelope and raw signed S10 query/observation. Its
only consumer takes `self` by value. It verifies S10 locally with the caller's
owner-pinned permit, holds the resulting non-`Clone`, non-serializable
projection as a local variable, and immediately lends it to the unchanged S12
verifier. The projection is never returned, serialized, persisted, or rebuilt
from scalar fields.

Rust ownership prevents mutation or reuse of that one handoff value. It does
not prevent another handoff from being constructed by re-verifying the same raw
signed evidence. Therefore S13 does not provide global exactly-once semantics
or durable replay consumption.

## Framing surface closure

S13 also closes the predecessor review's allocation-surface debt:

- S10's raw observation framer is module-private; sibling code receives only a
  fallible framer that validates all variable labels before allocation.
- S11's raw decision-message and sign-job framers are module-private; sibling
  code receives only fallible seams that validate request/signer labels and
  signer version first.

The 128-byte canonical-label boundary is tested at 128 and 129 bytes. Existing
S9-S12 known answers remain unchanged.

## What remains blocked

S13 has no provider, network, filesystem, database, cache, clock, retry,
Bridge, `StateStore`, BioCortex adapter, production trust-permit constructor, or
side-effect caller. It provides no evidence for:

- runtime availability or capture provenance of the exact S9 bytes;
- an external durable recovered-envelope source;
- a strict byte-only decoder and wire-schema policy;
- cross-process or restart-safe S10 projection delivery;
- provider linearizability, rollback protection, split-brain fencing, or key
  rotation/destruction;
- external database/KMS atomicity or S11 L2 persistence;
- currentness-at-use, replay consumption, downstream admission, or action.

S14 may define the strict byte-only decoder and external durable source
contract. It must carry raw signed S10 material across process boundaries and
re-verify it locally; it may not serialize or reconstruct the sealed S10
projection.
