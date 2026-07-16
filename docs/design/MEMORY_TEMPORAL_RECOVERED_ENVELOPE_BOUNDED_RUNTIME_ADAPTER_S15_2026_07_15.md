# BioCortex Track B S15: bounded recovered-envelope runtime adapter kernel

Date: 2026-07-15
Decision: `BLOCKED_FAIL_CLOSED`

## Outcome

S15 preregisters a private, default-off, production-neutral adapter kernel for
the exact S14 recovered-envelope source trait. The kernel turns an untrusted
runtime-shaped `open_exact -> read_into -> complete` byte stream into the
existing S14 bounded sink. It does not introduce a concrete transport, deploy
an external source, or change the historical-only result.

The adapter has one useful job: establish a real, executable state surface on
which later crash/restart, rollback, equivocation, and split-brain experiments
can inject faults without inventing a second source protocol. It is not itself
durability evidence.

```text
frozen caller-owned S14 exact lookup
                 |
                 | one open_exact; no retry/list/latest/cache/fallback
                 v
       private sealed S15 byte transport
                 |
                 | read_into caller-owned fixed buffer
                 | bounded positive progress + fixed step budget
                 v
       untrusted completion consistency receipt
                 |
                 | exact lookup commitment + revision + local len/hash
                 v
          unchanged S14 bounded sink
                 |
                 | unchanged strict R/E9/E10/P decode and signatures
                 v
       unchanged S13 -> S12 local verification
                 |
                 v
       private historical-only commitment
   NOT durability - NOT currentness - NOT admission
```

## Why the adapter precedes a durability model

S14 had an exact-object source trait and a 272 KiB bounded sink, but no
executable open/read/complete lifecycle. Building a durability model before
that lifecycle would only validate a model-specific protocol. S15 therefore
freezes the adapter state machine first. S16 may inject deterministic
crash/restart and rollback faults against this exact surface, while keeping
simulated evidence separate from external-provider evidence.

The repository's reference-provider offline harness is useful precedent for
that evidence separation, but its model rows are not evidence about this S15
source, any managed provider, or an owned durability lab.

## Frozen predecessor seam

S14 intentionally made its source trait, exact lookup, bounded sink, decoder,
and recovery entry point private and sealed. A sibling adapter would have to
copy the contract and could drift. S15 instead uses the established successor
pattern: the only production change to the S14 source is a feature-gated
child-module declaration, and the child directly implements the private S14
trait. A separately gated test-only fixture accessor lets S15 exercise the
unchanged full S14 -> S13 -> S12 path without copying the predecessor fixture;
it is absent from non-test builds.

That successor declaration changes the current S14 source blob. Consequently,
the S15 gate does **not** claim that the current HEAD passes the S14
historical-descendant gate. It checks the exact production child glue and
test-only fixture seam independently,
replays the frozen S14 integrated gate at `b2dd4706bd34155a1edd6d6472ee0b32a3bb232b`,
and reruns the unchanged 24 S14 tests with the S15 feature enabled. The S15
successor gate becomes the authority for the current tree.

## Adapter contract

The feature is
`temporal-evidence-s15-recovered-envelope-bounded-runtime-adapter-synthetic`.
It is absent from defaults and depends exactly on the S14 feature.

The private sealed transport exposes only:

1. one exact open using the already-frozen S14 lookup;
2. repeated writes into a caller-owned fixed-size buffer; and
3. one explicit terminal completion receipt.

The transport cannot return a `Vec`, `Box`, typed S9/S10 object, replacement
lookup, latest object, or list of candidates. S15 never normalizes, reframes,
or reconstructs evidence. It forwards only the raw byte sequence into the
unchanged S14 sink.

The lookup is frozen before the open. Response metadata is compared with the
request; it cannot generate or overwrite the expected identity or record
digest. Completion binds a domain-separated commitment of every exact lookup
field, the exact object revision, the locally observed byte length, and the
locally computed SHA-256. The record digest must also equal the digest already
pinned by S14. The completion receipt is untrusted consistency metadata, not a
signature, authorization, durability receipt, or currentness token. The
adapter and completion value are private, non-`Clone`, non-serde values; their
`Debug` output is redacted.

## State and bounds

Each adapter instance is one-shot:

```text
Fresh -> Opening -> Streaming -> Completed
  |         |           |            |
  +---------+-----------+------------+--> TerminalFailed on any violation
```

At most 1,024 positive `Data` steps are accepted; the following and 1,025th
transport read call must be terminal `Complete` and is not a data step. A
1,025th `Data` result fails. Reentry, a
second source read, an open failure, read failure, zero progress,
reported length beyond the caller buffer, checked-length overflow, S14 sink
cap/allocation failure, step-budget exhaustion, empty completion, or any
completion mismatch permanently fails that adapter instance. There is no
internal retry, replica switch, resumption, fallback, cache, or best-effort
return. Partial bytes are owned by the failing S14 call and cannot become a
historical result.

The fixed buffer and step budget bound adapter-local post-callback byte
processing and the number of successful data steps. They do not bound CPU used
inside a backend callback or prove that a future provider avoids internal
allocation, blocking I/O, deadlock, or an unbounded wait. S15 has no clock,
timeout, cancellation, async runtime, thread-safety claim, or remote resource
cleanup claim.

## Verification layering remains unchanged

The adapter does not directly construct an S13 handoff and has no production
caller for the S14 recovery entry point. After adapter completion, S14 still:

- checks the complete R digest pinned by the request;
- strictly decodes fixed-position, length-framed R/E9/E10/P bytes with exact
  EOF and all existing caps;
- verifies the source capture signature and exact cross-bindings;
- locally verifies raw signed S9 and S10 evidence; and
- consumes the existing S13 handoff through unchanged S12 verification.

A transport that forges completion metadata, mixes snapshots, truncates,
appends, or mutates bytes cannot bypass those layers.

## Explicit negative claims

S15 contains no filesystem, network, database, provider SDK, credential,
production source implementation, production permit constructor,
Bridge/`StateStore` caller, write/delete API, background task, or deployment
configuration. In particular, S15 does not prove or provide:

- external persistence, fsync, atomic rename, manifest ordering, or restart
  recovery;
- provider linearizability, availability, timeout behavior, or memory bounds;
- rollback resistance, non-equivocation, split-brain fencing, quorum, witness,
  current chain head, or global replay consumption;
- owner-authorized runtime object selection;
- actual capture, signer custody, rotation/revocation, or cryptographic role
  separation;
- currentness at downstream use, atomic consume-and-action, exactly once,
  admission, or a side effect.

An exact valid record may still be read and historically verified more than
once. The one-shot adapter instance is only a local misuse guard; it is not a
global replay fence.

## S16 preregistration

S16 should target the frozen S15 event/state surface with a deterministic
fault model covering at least:

- partial/torn object writes and object/manifest commit reordering;
- acknowledgement before durable commit and commit followed by response loss;
- crash at each open/read/complete cut and restart from durable bytes only;
- object-present/receipt-absent and receipt-present/object-absent states;
- old snapshot or generation restore, same-revision equivocation, stale
  replica, split brain, unavailable witness, and post-persistence bit flip.

Those rows must remain a simulated ledger and count as zero external durability
observations. Real admission remains blocked until separately authorized
provider or owned-lab evidence, owner-pinned production permits, runtime capture
attestation and signer separation, runtime S10 delivery, and atomic
currentness-at-use are available.
