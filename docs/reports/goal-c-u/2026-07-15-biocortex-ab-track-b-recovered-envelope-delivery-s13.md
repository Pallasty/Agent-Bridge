# BioCortex / Agent-Bridge Track B S13 report

Date: 2026-07-15
Outcome: `BLOCKED_FAIL_CLOSED`

## Result

S13 preregisters a private, default-off, owned S9 structural envelope and a
consuming in-process handoff. The handoff locally verifies typed signed S10
material and lends the sealed projection directly to the unchanged S12
historical verifier. Exact request/decision messages and the exact 64-byte S9
signature are independently checked and bound by a domain-separated structural
digest.

S10/S11 raw variable-label framers are now module-private; sibling code can use
only validated fallible seams. This closes the allocation-surface review item
without changing predecessor known answers.

## Authorization boundary

This is not a runtime or durable carrier. The handoff is one-shot only for one
Rust value and is not a global replay fence. There is no strict byte-only
decoder, capture provenance, external source, cross-process sealed projection,
production permit, currentness-at-use, Bridge/`StateStore` caller, transport,
admission, or side effect. Side effects unlocked: `NONE`.

## Verification

The independent Python checker rebuilds the S9 request/decision messages,
RFC 8032 signature, and S13 envelope digest without sharing Rust framing code.
It also checks the private ownership surface, validated S10/S11 framers,
default-off feature graph, absence of Bridge wiring, and the negative
authorization contract. Two isolated checker passes must byte-match the frozen
TSV receipt.

The low-memory Rust matrix is:

- S13: 15 tests;
- retained S12: 32 tests;
- S11 after framing hardening: 30 tests;
- S10 after framing hardening: 15 tests;
- retained S9: 15 tests.

The gate first replays the descendant-capable S12 gate from frozen baseline
`a3cb958e36743b3ce52b86a66e99ae2366b5bc89`, then checks the current source.
All Cargo work uses one job, no incremental compilation, and no debug info.
The source/integration detector accepts a single-parent source directly over
that baseline, an ordinary two-parent integration with that source as second
parent, or later first-parent descendants whose protected S13 blobs are still
identical.

## Artifact binding

- `crates/store/Cargo.toml`: `91125e9958c77b8821dbee3809a31a18dcc74c7db989ed1e8ef0bb75baa7c8d3`
- `crates/store/src/temporal_replay_transport/external_authority_operation_state_machine.rs`: `97a475a6b8a93f808b9a5a19e0ee28526b02ba7dddea4dbba4721c954997d896`
- `crates/store/src/temporal_replay_transport/external_operation_recovery.rs`: `7fe6101c2f099f71e103afac3bdb153a20c59a34333e5e3c585f5e111450055c`
- `crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification.rs`: `564165514a16ad59e5c717c476252473e7cba62d792c3a1c80a4c749c5707d6f`
- `crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery.rs`: `fc61ea04ff4d69083e3c4c1572dff3c05039e693874f94ea290cf896931e8b6e`
- `docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_DELIVERY_S13_2026_07_15.md`: `0297c7c900305c72f97b22531380f1023cbc61d2827201ec7fdb715e834af5ce`
- `docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-delivery-s13-v0.json`: `6bb6176822dac0bcf72a634ad4fc109cb7eed1d8b9d6e4b3d2e774852074b6a6`
- `docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s13-v0.json`: `99a005864ce23fd2236009af96891a81018f8e6e62dd87873739f90c74c374e6`
- `scripts/check-memory-temporal-recovered-envelope-delivery-s13.sh`: `03236755b02e49590bbe2b87c842afde1043b4d7daa88ecd18b54fd0baac7d71`
- `scripts/eval/check_memory_temporal_recovered_envelope_delivery_s13.py`: `f108c3de157ef9684f197559dd21ea6db7fe0a43e72ecaab0d4110ed2b5389a8`
- `scripts/eval/fixtures/memory_temporal_recovered_envelope_delivery_s13.expected.v0.tsv`: `e8d7a76221bbf9372a9826f21cc1f32ea4c01b1c233774fe18c92100477d43d6`
