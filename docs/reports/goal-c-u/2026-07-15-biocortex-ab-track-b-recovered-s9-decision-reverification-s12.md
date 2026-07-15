# BioCortex / Agent-Bridge Track B S12 report

Date: 2026-07-15
Outcome: `BLOCKED_FAIL_CLOSED`

## Result

S12 implements a private, default-off, pure historical re-verifier for a recovered S9 decision. It requires an already verified S10 `COMMITTED` projection, complete canonical S9 request/decision bytes, and an independently signed S11 L1 operation record. The output is non-serializable historical evidence; it is neither currentness nor admission.

The implementation uses shared predecessor verifier seams rather than reproducing S9/S10/S11 framing. It makes no provider/network/clock/cache/persistence/Bridge/`StateStore` call. S11 L2 revision and checksum are excluded and unread.

## Executable evidence

- S12 fixed-vector and negative suite: 32 tests.
- S9 original Ed25519 and S11 L1 Ed25519 roles use different key IDs and public keys.
- Complete canonical S9 request/decision bytes are byte-equality checked before detached verification.
- Verified S10 scope, operation, challenge, request, decision, journal, and revision fields are cross-bound.
- S11 authenticated L1 scope, operation, challenge, request, decision, snapshot, journal, and revision fields are cross-bound.
- The recovered S10 operation record must exactly match S11 L1 revision and sequence, and an authenticated S11 commit term above the S10 lookup term is rejected after re-signing.
- Rewriting S11 L2 revision/checksum leaves the historical commitment unchanged; corrupt L2 metadata is also ignored by S12.
- Historical `ACTIVE` remains historical after a later `REVOKED` observation and cannot become an admission token.

## Authorization boundary

No production owner trust anchor or approval receipt is present. No external carrier, durable recovered envelope, runtime S10 projection delivery, external database/KMS evidence, currentness-at-use atomicity, Bridge/`StateStore` integration, transport, or production admission is implemented. Side effects unlocked: `NONE`.

## Verification

Final low-memory gate results and the committed artifact digests are frozen below after review.
The source-bound custodian v1 pack is replayed from the frozen baseline archive
because its historical manifest intentionally binds the pre-S12 S9 source
bytes. The modified S9/S10/S11 glue is instead bound and checked by the S12
checker, exact delta gate, and predecessor/S12 Rust regressions.

The same gate also has an integrated mode. It requires an ordinary two-parent
merge whose second parent is the exact S12 source commit and whose first parent
contains the first-condition-output guard integration. It preserves all nine
guard packet blobs, permits only the three preregistered S9/S10/S11 glue hash
transitions, and replays the unchanged guard gate in a temporary clean
first-parent worktree. The old guard gate is deliberately not weakened to
accept successor glue bytes in the current tree. The merge tree must then pass
the S12 oracle and the complete Rust regression matrix before the integrated
marker is emitted.

## Artifact binding

- `crates/store/Cargo.toml`: `40bbcc10effa7137a5c0b08d2b89c70285b4b1503b441c732398b803d01e96dc`
- `crates/store/src/temporal_replay_transport.rs`: `f47f6ca04f347cc8b8c2d5f44308906f953ad78656fc27cfc141873a5c8f7f91`
- `crates/store/src/temporal_replay_transport/external_authority_operation_state_machine.rs`: `61ba010375d465ef36ef35cff4c8315ca2a577bae1d030ba085c4aec6d68ea1c`
- `crates/store/src/temporal_replay_transport/external_operation_recovery.rs`: `f9a27f30f7928dd97de2bc7bc4a0d550bd957feb7dd7125dccfde7d40188da27`
- `crates/store/src/temporal_replay_transport/external_restore_authority.rs`: `431c5d145682d4b13b244c7dcf6fefba0252f1d212e64a5593625b3088ff5322`
- `crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification.rs`: `1665def3ed58292d49980b71a2d5bfb9ced0e071542f7bfffb391054b058e3c2`
- `docs/design/MEMORY_TEMPORAL_RECOVERED_S9_DECISION_REVERIFICATION_S12_2026_07_15.md`: `28ccebca75bb016e741df8ff471c522bcd2ec5b6513a530164073f1c0ec1142f`
- `docs/design/fixtures/biocortex-ab-track-b-recovered-s9-decision-reverification-s12-v0.json`: `4efa9dc533cfca6c98473ae20cf8fc983292362e92b669575a81e80e189b1303`
- `docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s12-v0.json`: `7a580c64ae736a3dd8257af8fd2a81a027ecfe4cbf85fb3205bd25b6a25d9eb6`
- `scripts/check-memory-temporal-recovered-s9-decision-reverification-s12.sh`: `df9d0d6a358262773dbed9a2d5ca8d0ba375476542399c2a829b39367afa42d5`
- `scripts/eval/check_memory_temporal_recovered_s9_decision_reverification_s12.py`: `d580feaad194579961b380dcbea5aca4eb95101b3ce76beac793a248b3ea4dd2`
- `scripts/eval/fixtures/memory_temporal_recovered_s9_decision_reverification_s12.expected.v0.tsv`: `d85e72929f6bffec02c728a458821081fc0358fa86881e40ebf4ec8c2b3fb3f1`
