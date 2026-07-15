# BioCortex / Agent-Bridge Track B S14 report

Date: 2026-07-15
Outcome: `BLOCKED_FAIL_CLOSED`

## Result

S14 preregisters a private, default-off exact recovered-envelope source. A
sealed source contract streams one record into a 272 KiB bounded sink, after
which a strict byte-only decoder reconstructs exact canonical S9 and raw signed
S10 evidence. A source-signed provenance message cross-binds E9, E10, their
inner messages, the S13 envelope, and the source identity before the unchanged
S13/S12 historical verifier is consumed.

The result remains private, move-only, and historical-only. There is no
production source or permit constructor, runtime adapter, external durability
proof, currentness-at-use, replay consumption, Bridge/`StateStore` caller,
admission, or side effect.

## Strict source and provenance boundary

R, E9, E10, and P use fixed-position `u64be length || exact bytes` frames with
fixed counts and exact EOF. Labels are checked as canonical ASCII at 128 bytes
before `String` allocation; fixed commitments and signatures require exact
32/64-byte widths. Checked conversion, checked offsets, remaining-byte checks,
aggregate limits, and `try_reserve` precede attacker-controlled growth.

The source permit now rejects invalid scope labels, zero identities, policy,
public key, signer version, and revision floor. A validly re-signed S10 record
that is independently authentic but mismatched with a valid S9 record is still
rejected by the final S13/S12 cross-binding.

P's `object_size` is exactly `len(E9) + len(E10)` and its
`raw_object_sha256` is the domain-framed E9+E10 digest; neither describes full
outer R. The lookup separately pins full R's digest. The source signer is a
separately pinned logical role only: S14 neither enforces nor attests
cryptographic key separation from the S9/S10/S11 signers. Exact lookup also
does not prove owner-authorized runtime object selection.

## Authorization boundary

A valid source signature proves only that the permit's key signed exact P
bytes. It does not prove actual capture, crash/restart durability, newest-head
selection, rollback resistance, non-equivocation, split-brain fencing, signer
custody, signer role separation, or owner-authorized runtime selection. A
repeated record can be reverified again, demonstrating that S14 is not a global
exactly-once or replay fence. Side effects unlocked: `NONE`.

## Verification

The independent Python checker rebuilds the canonical S9 request/decision,
S10 query/observation, E9, E10, P, source Ed25519 signature, full R, and sourced
historical-chain known answers without importing the Rust decoder. It also
checks the private/default-off surface, exact frame counts, bounded allocation
order, permit validation, logical signer semantics, negative authorization
claims, and absence of Bridge wiring. Two isolated passes must byte-match the
frozen TSV receipt.

The low-memory Rust matrix is:

- S14: 24 tests;
- retained S13: 15 tests;
- retained S12: 32 tests;
- retained S11: 30 tests;
- retained S10: 15 tests;
- retained S9: 15 tests;
- `ab-store` checks with and without S14, plus `ab-bridge` without defaults.

The gate replays the complete S13 gate at frozen baseline
`b9988aa5772928fb964c8d47b4f294a69f5122ac`, then verifies the S14 source.
Cargo is serial, non-incremental, and built without debug information. The
frozen nested predecessor replay receives only the validated offline Cargo
registry cache through its private HOME. Its HOME, configuration, and
top-level writable Cargo state remain isolated; the trusted offline registry
cache is deliberately shared. The
source/integration detector accepts a single-parent source directly over that
baseline, an ordinary two-parent integration with the exact S14 source as
second parent, or later first-parent descendants whose eight-file S14 packet
remains byte-identical. Cargo and parent-module glue may evolve in successors.

## Frozen known answers

- source public key:
  `278117fc144c72340f67d0f2316e8386ceffbf2b2428c9c51fef7c597f1d426e`;
- E9: 1,970 bytes,
  `c850a905563c7f67d8cf145b65619deb89780cfca12baa8a70b8a1856e27bfcd`;
- E10: 1,898 bytes,
  `61e4decbd7bb4cc6025f459e41c451d30124b084a2afaa20b2fe356eb259808e`;
- E9+E10 evidence payload: 3,868 bytes, domain-framed digest
  `5832d8777bdf22aa0b4a4bcaa70300c5dfc6fa87b100747438cb730e9d69a8db`;
- P: 1,206 bytes,
  `e7a90fa8f378e8d8dfa1d3cedf9d8db73167f729357aecb003ffac93138ab52e`;
- R: 5,494 bytes,
  `a788ec43fefa76e393d77c86bbfabeef7d2ae8c5499bb834c1945af5cbb1b3cd`;
- unchanged S12 historical chain:
  `afb8aa4945f0e491937f75233c621d52f1bcc1307e6d497352fd9d0fc79b7204`;
- S14 sourced historical chain:
  `d29da2a081b09b2b124298eae40b15ada555196cc5e3fd52d8e4dfadf3f2149b`.

## Artifact binding

- `crates/store/Cargo.toml`: `04aa49f8706a6e2ac99acfb87ee7f54dd88796b55fb8992e7c68a3323ee2d609`
- `crates/store/src/temporal_replay_transport/external_operation_recovery.rs`: `add0113d523c258b3da7251d1958928dfc5cfb65a9678c70032a0de93bf51cba`
- `crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery.rs`: `92691b906b6292fec9f3dfd28e2b1320059fce087c1f2d3174c596b6a22d07e1`
- `crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source.rs`: `751b746180a8bd03e4f714527a703d4aa81ee6ccc861d65ecd02921972933255`
- `docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_SOURCE_S14_2026_07_15.md`: `46f33ba93d7299e2ce9979c10326d531205045415214bfeec8a96312f7b4507b`
- `docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-source-s14-v0.json`: `ba10e9f433294e8d9f50f3342f04ec140ff2f7fce8e3f2c02130a5a0b4f92899`
- `docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s14-v0.json`: `60810b69a50202b4824512c34977a7c462d47c0beab4d061c67c7b7ac4d29c98`
- `scripts/check-memory-temporal-recovered-envelope-source-s14.sh`: `095ae3b50ed8f10d55d20d98041aabafddef362af67b734c83c69436e98cce7e`
- `scripts/eval/check_memory_temporal_recovered_envelope_source_s14.py`: `3d89b9f4a44bb8dd978b538cf72e2c94f2ed2d8c461c7d85e604e82326381abe`
- `scripts/eval/fixtures/memory_temporal_recovered_envelope_source_s14.expected.v0.tsv`: `1105dbb42cc0f24578a526a039dd31363a92874f8c9e188b7c1aaddcc84ae4b4`
