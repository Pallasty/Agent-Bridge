# S14 strict recovered-envelope source

Date: 2026-07-15
Decision: `BLOCKED_FAIL_CLOSED`
Scope: private, default-off, synthetic preregistration

## Outcome

S14 closes the local representation and parsing gaps left by S13:

1. a private sealed source contract can stream one exact object into a bounded
   sink without first handing Agent-Bridge an unbounded allocation;
2. a strict byte-only decoder reconstructs exact S9 request/decision material
   and exact raw signed S10 query/observation material;
3. an Ed25519 key pinned for the logical source-signing role verifies a
   capture-provenance claim that cross-binds the exact source identity, source
   object, E9, E10, S13 envelope, and inner-message digests;
4. the decoded raw S10 evidence is re-verified locally and its sealed
   projection exists only while the unchanged S13 handoff calls S12.

The result is a private historical source commitment. It is not a deployment,
currentness token, admission capability, durable replay fence, or side-effect
authorization.

## Boundary

```text
private sealed exact source contract
             │ streams chunks into 272 KiB bounded sink
             ▼
  R = exact source record bytes
             │ strict fixed-frame decoding
             ├── E9: exact S9 request + decision + signature
             ├── E10: exact S10 query + observation + signature
             └── P: source-signed capture claim
                         │
                         ▼
             S13 owned envelope + consuming handoff
                         │ local S10 verification
                         │ sealed S10 projection remains lexical
                         ▼
                   unchanged S12 verifier
                         │
                         ▼
             private historical-only commitment
        NOT durability · NOT currentness · NOT admission
```

There is no production source implementation, filesystem/network/database
adapter, production permit constructor, Bridge/`StateStore` caller, retry,
cache, clock, list/latest lookup, write, delete, or fallback.

## Strict wire

Every layer uses `u64be length || exact bytes`, a fixed frame count, a fixed
position for every field, and exact EOF. There are no tags, aliases, optional
fields, defaults, JSON, serde, normalization, or ignored trailing bytes.
Repeating or reordering a frame changes its positional meaning and fails exact
identity or typed re-encoding.

```text
E9 = frame(S9_WIRE_DOMAIN,
           policy, profile, schema,
           S9/S10/S11/S12/S13 contract hashes,
           exact S9 request message,
           exact S9 decision message,
           exact 64-byte S9 signature)

E10 = frame(S10_WIRE_DOMAIN,
            policy, profile, schema,
            S9/S10/S13 contract hashes,
            exact S10 lookup-query message,
            exact S10 observation message,
            exact 64-byte S10 signature)

P = frame(CAPTURE_PROVENANCE_DOMAIN,
          source scope/incarnation/generation,
          exact source object id/revision,
          exact evidence-payload size = len(E9) + len(E10),
          exact evidence-payload hash = SHA256(frame(RAW_OBJECT_DOMAIN, E9, E10)),
          len/hash(E9), len/hash(E10),
          S13 envelope digest,
          S9 request/decision digests,
          S10 query/observation digests,
          capture id/sequence,
          producer/build/policy/predecessor commitments,
          logical source signer id/version)

R = frame(SOURCE_RECORD_DOMAIN,
          policy, profile, record schema, S13 contract hash,
          E9, E10, P, exact 64-byte source signature)
```

The S10 query now has a validated exact-message seam. Its existing digest is
the SHA-256 of that same message, so predecessor known answers do not change.
Raw framers remain private.

## Decoder and allocation rules

The decoder receives only bytes. It never accepts caller-supplied typed S9 or
S10 values alongside those bytes. For every frame it performs:

- checked `u64 -> usize` conversion;
- checked prefix and end offsets;
- remaining-length validation before slicing;
- fixed frame-count and exact-EOF validation;
- ASCII/canonical-character and 128-byte label checks before allocating a
  `String`;
- exact 32-byte digest/ID, 8-byte integer, and 64-byte signature checks.

After parsing, shared S9/S10 validated framers rebuild each canonical message
and require byte-for-byte equality. E9/E10 components are independently capped
at 128 KiB, their framed wires at 132 KiB, provenance at 4 KiB, and R at
272 KiB.

The source does not return `Box<[u8]>`. It streams into a private sink whose
`checked_add`, cap check, and `try_reserve` happen before `extend_from_slice`.
An equal-to-cap stream is accepted by ingress; cap plus one is rejected without
growing the buffer.

## Source and provenance semantics

The source trait is private and sealed and exposes only one exact-version read.
The lookup pins source scope, incarnation, generation, object ID, revision, and
the complete record digest. Every source failure maps to the same fail-closed
result with no retry, cache, or fallback.

The capture permit is owner-pinned in tests and has no production constructor.
It pins a distinct logical source-signing role, but S14 does not enforce or
attest that its key material differs cryptographically from the S9, S10, or
S11 signer keys. A valid signature proves only that the pinned source key
signed exact P bytes. It does not prove:

- that the capture actually occurred at the claimed time or system;
- that bytes were durably persisted across a crash or restart;
- that the record is the newest object or current chain head;
- that the source is linearizable, non-equivocating, or rollback-safe;
- that signer custody, rotation, revocation, or destruction is production-safe.

Within P, `object_size` is `len(E9) + len(E10)` and `raw_object_sha256` is the
domain-framed E9+E10 evidence-payload digest. Neither names the complete outer
R bytes. The exact digest of complete R is a separate lookup field,
`expected_record_sha256`; neither binding proves external durability or
owner-authorized runtime object selection.

Source revision, capture sequence, S9 authority revision, and S10 journal
revision are four independent semantic domains. S14 never equates or orders one
domain using another.

## Ownership and output

The bounded record, decoded record, verified capture, S13 envelope, S13
handoff, and final sourced historical value are private and move-only. They
derive neither `Clone` nor serde traits. Debug output is fully redacted.

The final `historical_source_chain_sha256` binds R, P, E9, E10, the E9+E10
evidence-payload commitment, and the unchanged S12 historical chain. Re-reading
the same valid record can create another historical result. That behavior is
intentional negative evidence that S14 is not a global exactly-once mechanism.

## Frozen known answers

- source public key:
  `278117fc144c72340f67d0f2316e8386ceffbf2b2428c9c51fef7c597f1d426e`;
- E9: 1,970 bytes,
  `c850a905563c7f67d8cf145b65619deb89780cfca12baa8a70b8a1856e27bfcd`;
- E10: 1,898 bytes,
  `61e4decbd7bb4cc6025f459e41c451d30124b084a2afaa20b2fe356eb259808e`;
- provenance: 1,206 bytes,
  `e7a90fa8f378e8d8dfa1d3cedf9d8db73167f729357aecb003ffac93138ab52e`;
- source record: 5,494 bytes,
  `a788ec43fefa76e393d77c86bbfabeef7d2ae8c5499bb834c1945af5cbb1b3cd`;
- S13 envelope remains
  `5d74c7a300abe503b9a79c796394faa23de0c64f22fb80902294fa0654ee15d9`;
- S12 historical chain remains
  `afb8aa4945f0e491937f75233c621d52f1bcc1307e6d497352fd9d0fc79b7204`;
- sourced historical chain:
  `d29da2a081b09b2b124298eae40b15ada555196cc5e3fd52d8e4dfadf3f2149b`.

## What remains blocked

S14 does not supply a runtime producer or external durable store. It has no
crash/restart evidence, source ledger, anti-rollback state, split-brain fence,
production trust anchor, owner-authorized runtime exact-object selection,
capture signer custody or cryptographic role-separation evidence, runtime raw
S10 delivery, currentness-at-use, atomic consume-and-action boundary,
admission, or side effect.

S15 may preregister a production-neutral runtime adapter and durability fault
model for the exact S14 source contract. It must preserve bounded streaming,
exact-version reads, raw S10 local re-verification, and all fail-closed negative
claims; adapter existence alone may not be treated as durability or admission.
