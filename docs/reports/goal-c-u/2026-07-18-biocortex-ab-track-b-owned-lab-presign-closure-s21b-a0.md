# BioCortex Track B S21B-A0 pre-sign closure audit report

Date: 2026-07-18

Stage: **S21B_A0_NON_LIVE_PRESIGN_CLOSURE_AND_ROLE_ARTIFACT_EXISTENCE_AUDIT**

Status: **S21B_A0_BLOCKED_MISSING_ROLE_ARTIFACTS_AND_REPRODUCIBLE_CLOSURES**

Decision: **S21B_A0_REMAINS_BLOCKED_NO_UNSIGNED_SUBJECT_OR_OWNER_SIGNING_REQUEST**

Implementation mode: **READ_ONLY_IDENTITY_AND_EXISTENCE_AUDIT_WITH_SYNTHETIC_BLOCKED_RECEIPT_ONLY**

Owner interaction required now: **NO**

Live execution: **NOT AUTHORIZED, NOT IMPLEMENTED, AND NOT ATTEMPTED**

Side effects unlocked: **NONE**

## Outcome

S21B-A0 closes the ambiguity between a syntactically valid SHA-256 string and
an artifact that was actually defined and reproducibly built. It audits the
immutable S21A integration at
`34b1c7e6ca9c2b75fd2ef3cf418a444353059511`, not a moving remote branch, and
then hard-blocks advancement because that archive contains none of the four
required named role binaries.

This is a useful blocked result. It prevents a test executable, private library
module, unrelated binary, or arbitrary nonzero digest from being relabelled as
the controller, observer, runner, or validator. It emits no unsigned final
subject and no owner signing request or signing message. The user therefore has
nothing to sign during A0.

## Independently reconstructed target

The checker selects its Git identities from constants in the checker rather
than from a candidate receipt. It reconstructs:

- source commit `ed5d959489f88d0eead21b604d03a142e0584982` and tree
  `7d1db2c9eb04d75cc980ea83d369b9129155252f`;
- source parent `33c2c4df78ef302fd0538986b95fa40a3711ba86` and tree
  `6f92c687b61e1433e693ca6cd1bc6390dda97f29`;
- integration tree `00bbf534c33ecfa56d05579d8a7f4c83e60b208e`;
- ordered integration parents
  `8521ff6a9784a6d74be2b8ee0e02f3aba6b9f8a5` and
  `ed5d959489f88d0eead21b604d03a142e0584982`;
- exact `tar.umask=0022` archive size `48,107,520` bytes and SHA-256
  `d45312d5b343dd036ef6906af0abe9f59da8220cf6ef16fb87caf8c1265c0bb5`;
  and
- raw `Cargo.lock` SHA-256
  `408e0aa5e6bc3f2a318719c57419ece60b507df0a11c1738fd40dda66aac1f59`.

The release gate independently writes and hashes the same archive, extracts it
under a private `0700` scratch root, rejects symlinks and group/world-writable
materialization, and checks the extracted `Cargo.lock`. It does not require the
remote branch to remain at an old observation head.

## Role-artifact finding

The target archive contains 16 Cargo manifests and four unrelated declared
binary targets. Their sorted-name-set SHA-256 is
`ee27046b1bae09e98d51f2c4997e9fc4fac88eeae09b948c106a8c32e6d5d95c`.
The exact required names are absent:

1. `ab-owned-lab-controller`;
2. `ab-owned-lab-observer`;
3. `ab-owned-lab-runner`; and
4. `ab-owned-lab-validator`.

Present count is zero and missing count is four. The checker deliberately
requires this exact absence for the A0 blocked KAT; an unexpected appearance is
a target change and hard-fails rather than silently advancing the stage.

The toolchain-manifest, feature-set, schema-set, deterministic per-role build
recipe, two independent clean-archive rebuild receipts, and rebuild equality
receipt are also absent. A later implementation of any of them changes the
repository identity and must be integrated and refrozen before subject
generation.

## Closed receipt and negative validation

The committed receipt is synthetic, test-only, blocked, and non-authorizing. It
uses closed local-reference-only Draft 2020-12 schema
`agent_bridge.memory_temporal_owned_lab_presign_closure_receipt_s21b_a0.v0`.
Its raw fixture SHA-256 is
`62bf0e62a8e1833418249cf7b5c8e54ea1d16eaf39c80936d1a9c98616c2f46e`,
and its independently recomputed domain-separated self digest is
`94a0725563faa6a4e59a4f255f47bc2786d75a43ab17933a2dd039b9737c3380`.

The checker produces 41 stable TSV rows. Two ordinary seeds and one mutation
self-test seed must be byte-identical to the checked-in expected receipt. The
self-test applies 33 directional mutations covering identity drift, role
artifact fabrication, closure fabrication, forbidden signing/authority/live
claims, malformed canonical framing, and schema closure. Every mutation must
be rejected before the stable blocked receipt is emitted.

## Release gate

The release gate accepts either the exact one-commit A0 source packet or an
ordinary two-parent integration whose second parent is that source. It freezes
an exact `10A` packet delta and verifies that every packet blob and Git mode is
unchanged between source and integrated HEAD.

The `fast` tier performs Git identity/topology checks, private archive
materialization, seed determinism, negative self-test comparison, expected TSV
comparison, and this report's closed hash table. It is explicitly non-release.

The `full-replay` tier performs the same checks and invokes the immutable S21A
release gate exactly once in its own no-hardlink detached clone. That predecessor
gate already performs its serial offline Rust and frozen S20B replay, so A0 does
not add a second independent copy of the deep chain. The invocation supplies
`CARGO_BUILD_JOBS=1` and `RUST_TEST_THREADS=1`; final execution remains subject
to the outer bounded-memory scope.

Neither tier reads an external owner private key or generates or emits a usable
owner-signature artifact. The frozen predecessor KAT may create ephemeral
in-memory test keys and signatures, which remain synthetic and are never an
owner artifact or authority. Neither tier emits a signable subject or signing
message, starts a canary, or unlocks side effects.

## Advancement boundary

S21B-A1 may begin only by defining and building all four exact role binaries and
the missing canonical closure profiles. It must produce two isolated builds
from clean archives, prove byte equality for every role and closure digest, and
integrate those changes into a new refreeze identity. A separate review must
then pass before an unsigned subject can be generated.

Owner trust-anchor provisioning and owner signing remain later steps. No owner
signature command is included in this report because presenting one now would
misrepresent an incomplete closure as ready for review.

Hash table state: **FINAL_CLOSED_WORLD_BOUND**

## Final artifact digest table

| Path | SHA-256 |
|---|---|
| docs/design/MEMORY_TEMPORAL_OWNED_LAB_PRESIGN_CLOSURE_S21B_A0_2026_07_18.md | a45a324375f2ed0b642cbf9375136255112841b6708ea4ff0ab0bdc2fb9a0a4b |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-presign-closure-contract-s21b-a0-v0.json | 63a5db84466465e52a2dfffa8a7792b741b180d447debb62663fbdd1e4b2eb6e |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-presign-closure-status-s21b-a0-v0.json | 7269ef379bc3924464c3c6a7bbcb38d3a8851515639c36f0a16432a90b2da294 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-presign-closure-receipt-schema-s21b-a0-v0.json | f4f73651375f26f9a08bd91b5642c7e2c9c6679fec463357c5d6474f853ca510 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-presign-closure-receipt-synthetic-s21b-a0-v0.json | 62bf0e62a8e1833418249cf7b5c8e54ea1d16eaf39c80936d1a9c98616c2f46e |
| docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s21b-a0-v0.json | db6a8775dcf951a5b82e6c098171f7f193805f8b241c6c09bdd7b0e9286a9e5d |
| scripts/eval/check_memory_temporal_owned_lab_presign_closure_s21b_a0.py | f4f698b7c4edb374123bd32c6d53cbdbbc63d1d3b4dafb369d269d82f49e016d |
| scripts/eval/fixtures/memory_temporal_owned_lab_presign_closure_s21b_a0.expected.v0.tsv | eae895c793395189adda0ebee209282b7b1ad2797d5eb233d1f815b51d2f1d99 |
| scripts/check-memory-temporal-owned-lab-presign-closure-s21b-a0.sh | 0107aa0fef87894c7d762fea3e01f58bb81071235c09fff5376adacf12d997a0 |

## Nonclaims

- This report is not an unsigned final subject or owner authority.
- The synthetic receipt is not real build evidence or a signing request.
- A known Git archive digest is not a reproducible four-role build closure.
- No anchor, private key, signature, external-input admission, permit, runner
  handle, executor, provider authority, or production authority is present.
- `live_canary=NOT_RUN` and `side_effects_unlocked=NONE`.
