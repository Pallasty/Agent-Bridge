# BioCortex / Agent-Bridge Track B S15 report

Date: 2026-07-15
Outcome: `BLOCKED_FAIL_CLOSED`

## Result

S15 preregisters the first executable runtime-shaped adapter for the private
S14 recovered-envelope source contract. A default-off child module implements
the existing sealed source trait using one exact open, a caller-owned 16 KiB
buffer, at most 1,024 positive data steps followed by one terminal completion,
incremental length/SHA-256 accounting, and
an explicit untrusted completion receipt. Raw bytes then continue through the
unchanged S14 strict decoder and S13/S12 local verifier.

This is an adapter kernel, not a concrete transport. It adds no filesystem,
network, database, provider SDK, credential, production permit, Bridge or
`StateStore` caller, deployment, durability proof, currentness, admission, or
side effect. Real provider/runtime observations: **0**.

## One-shot fail-closed state surface

Each adapter instance moves from fresh to opening, then streaming, then either
completed or terminally failed. Every later read or reentry fails. The adapter
performs exactly one `open_exact`; it has no retry, cache, fallback, replica
switch, resume, list/latest, range assembly, write, or delete path.

The transport only writes into the caller-owned fixed buffer. `Data(0)`, a
reported length beyond that buffer, checked-length overflow, the inherited
272 KiB S14 cap, allocation failure, read failure, step exhaustion, or empty
completion all fail closed. Partial bytes cannot produce a historical result.

The request lookup is frozen before open. Completion cross-checks a
domain-separated commitment of the full exact lookup, exact revision, and the
locally observed length and digest; response metadata never replaces request
metadata. The receipt remains untrusted consistency information. It is not a
signature, owner approval, durability receipt, provider attestation, or
currentness token.

## Unchanged verification chain

The adapter neither accepts typed S9/S10 input nor reconstructs or normalizes
wire evidence. It forwards one byte sequence to the existing S14 sink. S14
still verifies the complete pinned record digest, exact fixed-frame EOF,
capture signature and cross-bindings, raw S9/S10 signatures, and then consumes
the existing S13 handoff through S12.

The frozen known answers remain:

- source record R: 5,494 bytes,
  `a788ec43fefa76e393d77c86bbfabeef7d2ae8c5499bb834c1945af5cbb1b3cd`;
- S13 envelope:
  `5d74c7a300abe503b9a79c796394faa23de0c64f22fb80902294fa0654ee15d9`;
- S12 historical chain:
  `afb8aa4945f0e491937f75233c621d52f1bcc1307e6d497352fd9d0fc79b7204`;
- S14 sourced historical chain:
  `d29da2a081b09b2b124298eae40b15ada555196cc5e3fd52d8e4dfadf3f2149b`;
- S15 exact-lookup commitment:
  `866e016ce631433e3e272d0858906f3c76c67204cd74b73ab11b7353e57eae00`.

## Frozen predecessor handling

The only S14 production-code change is the exact S15 child-module declaration.
A fixture accessor inside the S14 `cfg(test)` module, additionally gated by the
S15 feature, supports full-chain tests without copying S14 fixtures and is
absent from non-test builds. No production or externally visible predecessor
item is made public, and no production constructor or caller is added.

Because that deliberate successor seam changes the S14 source blob, this
report does not claim that the current S15 HEAD passes the S14
historical-descendant gate. The S15 gate independently checks both allowed
glue hunks, replays the frozen S14 integrated gate at
`b2dd4706bd34155a1edd6d6472ee0b32a3bb232b`, and executes the unchanged S14
tests with the S15 feature. The current tree is governed by the S15 successor
gate.

## Verification boundary

The independent checker validates duplicate-free, root-closed contract JSON;
exact default-off feature dependency; lookup framing and known answers; fixed
bounds; state/failure taxonomy; the exact S14 successor seam; private sealed
surfaces; and absence of production or Bridge wiring. Its receipt is compared
byte-for-byte with a frozen TSV.

The low-memory gate uses one Cargo job, disables incremental compilation and
debug information, and keeps temporary clones and targets on `/Data` rather
than tmpfs. It serially checks the S15 tests, retained S14 through S9 matrices,
feature-on/off `ab-store`, and feature-off `ab-bridge`. A pass demonstrates
local implementation conformance only; it does not increase the count of
external durability observations.

The frozen non-ignored Rust matrix is S15 13, S14 24, S13 15, S12 32, S11 30,
S10 15, and S9 15 tests. The S15 cases include every two-chunk cut of a bounded
fixture, every partial-failure cut, all nine transport failure classes,
completion-binding mutations, exact/cap+1 ingress, 1,024/1,025 data-step
boundaries, forged/mixed bytes, a real open/read callback reentry, and an
end-to-end unchanged historical-chain known answer.

## Artifact binding

The source gate requires these exact SHA-256 bindings from the S15 source
commit; the report itself is excluded to avoid a self-referential digest.

- `crates/store/Cargo.toml`: `0771ce3868c826182d5ed03ccbf5a4bdd3fc6de24c10f1110108ebc36c80b3f1`
- `crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source.rs`: `fbc08e5c3fa312d0277b7ae3f1255270e84b3bf190452f14b4ca3261435a6cf8`
- `crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter.rs`: `be722ae5d61cf2d120c9d30685ab90d453c2e713ca08edfc0754621e8dabee3a`
- `docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_BOUNDED_RUNTIME_ADAPTER_S15_2026_07_15.md`: `0ce11e4fc3267bba92341899acab86d28864385a18618ee108b7ffdb2bfcfd98`
- `docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-bounded-runtime-adapter-s15-v0.json`: `07d7ae5e7345bb5052aa130349af2e90bae853e5c74560346a4178b2b0397cc7`
- `docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s15-v0.json`: `646b631581f96144d5af11ac50a53bdbfd9873ecb861b9cf8c046f9dd3905c02`
- `scripts/check-memory-temporal-recovered-envelope-bounded-runtime-adapter-s15.sh`: `01baf4f105189c1a7ce583e0814969903ef5bc4834df6ade9fd53e70fcf30eaa`
- `scripts/eval/check_memory_temporal_recovered_envelope_bounded_runtime_adapter_s15.py`: `024595e8c0263d98451594b1f6ca567e5b44340a7cb13aae8bf0000ac4e66c11`
- `scripts/eval/fixtures/memory_temporal_recovered_envelope_bounded_runtime_adapter_s15.expected.v0.tsv`: `b63540b72c4d4b95a42a7b73889e790b501121d3839c9d99380b8d3af39c3d49`

## Authorization and durability boundary

The S14 permit still does not prove owner-authorized selection of the requested
object. Exact bytes and a valid capture signature do not prove newest-head
selection, external persistence, fsync/rename ordering, crash recovery,
rollback resistance, non-equivocation, split-brain fencing, signer custody,
or key-role separation. The fixed ingress buffer does not bound provider
allocation or blocking, and the step budget is not a wall-clock timeout.

Repeated exact reads can still produce repeated historical verification. The
adapter's one-shot state is a local misuse guard, not a global replay fence or
exactly-once mechanism. Side effects unlocked: `NONE`.

## Next stage

S16 is preregistered against this exact state surface. Its synthetic fault
family covers partial/torn writes, object/manifest ordering, acknowledgement
versus durable commit uncertainty, crash/restart at every state cut,
object/receipt asymmetry, old snapshots, generation rollback,
same-revision equivocation, stale replicas, split brain, witness loss, and
post-persistence corruption.

S16 model rows must remain separate from provider or owned-lab observations
and count as zero external durability evidence. Production admission remains
blocked pending concrete runtime transport, owner-pinned permits, independently
authorized durability and anti-rollback evidence, runtime capture/custody and
role-separation evidence, runtime S10 delivery, and atomic currentness-at-use.
