# BioCortex Track B S21B-A1 role-build closure preregistration

Date: 2026-07-18

Stage: **S21B_A1_DEFINE_AND_BUILD_FOUR_NAMED_NON_LIVE_ROLE_ARTIFACTS_AND_REPRODUCIBLE_CLOSURES**

Status: **S21B_A1_TOOLING_COMPLETE_PENDING_POST_INTEGRATION_DOUBLE_REBUILD**

Decision: **S21B_A1_ADVANCE_ONLY_TO_SEPARATE_UNSIGNED_SUBJECT_CONTRACT_REBINDING_AND_GENERATION_REVIEW_NO_OWNER_SIGNING_REQUEST**

Owner interaction required now: **NO**

Live execution: **NOT AUTHORIZED, NOT IMPLEMENTED, AND NOT ATTEMPTED**

Side effects unlocked: **NONE**

## Preregistered outcome boundary

This is a preregistration report, not a completed-build report. S21B-A1 defines
the four exact named identity-only Cargo binaries, their canonical closure
manifests, an external receipt schema, and the offline procedure needed to
rebuild a future integrated target twice. The final A1 integration identity
does not yet exist. Consequently this report records no final target digest,
binary digest, identity digest, completed-build recipe digest, completed build
observation, or equality result. It does bind the final 24-file source packet
closure below; the report itself is deliberately excluded to avoid a
self-referential digest cycle.

The committed synthetic receipt remains in state
`SYNTHETIC_KAT_TOOLING_COMPLETE_PENDING_POST_INTEGRATION_DOUBLE_REBUILD`. Every
future target and build-evidence field is null, every completion/equality claim
is false, and `terminal_hard_lock=true`. Its purpose is to prove the blocked
shape and negative boundary without manufacturing evidence.

## Frozen predecessor observation

The immutable S21B-A0 predecessor is integration commit
`d677e923442661a1d896185923b244d22b726319`, tree
`4534149eb9c8057d4980f008897c9587bd253c7f`, and ordered parents
`908412b8209056a90b3be5c2f93896c763d31311` and
`4f627b0f1be2c858615906e5170055d92b5632b3`. Under the exact
`tar.umask=0022` archive profile, its observed archive is `48793600` bytes with
SHA-256 `6d2163035d98bb64a76fcbcb1c725d315cada415814f7a0cf82c7afc89c1cac8`;
its raw `Cargo.lock` SHA-256 is
`a0ba6e432b188cbd0e3157693cb586bb950584860f036f83ee535fe67284b709`.

These observations bind predecessor replay only. A real A1 receipt must select
the future source and integration commits from checker constants or explicitly
caller-pinned invocation inputs, parse their raw Git objects, and independently
recompute all relationships and contents. Candidate-carried expected values
are never authoritative.

## Refrozen A1 construction base

After the original source validation, GitHub `master` advanced and changed
`Cargo.lock` for the OAuth/JWT/RSA closure. A1 therefore does not discard those
upstream dependencies or exempt the lock from byte equality. Its separately
pinned construction base is commit
`a5c70f235cf4e1bffa26253e2618e0a0903c9a16`, tree
`35987f0ca61b200a34aa82b099482b791ed06bca`, with ordered parents
`66f4754fd871169f50f345e5c023c94466f8ffd4` and
`dc71c6f27aa1b9f310e5fff9e4e855011104dc96`. The base archive is `50216960`
bytes with SHA-256
`c8cd17b51792a695239f3569be728d1777fa3e5f98fa22d4489f21c8036892bf`;
its raw lock SHA-256 is
`452da4a2c2e4712251ad7a4076a3966222507eaf1695ff3d4ecab13084d732d2`.

The A1 lock is exactly that base lock plus the single zero-dependency local
role-package stanza. Its SHA-256 is
`726a447607f32fe6bbc05b9a75b5614cff8f0dc6561f51f0632ccc2459a7af30`;
it contains 580 packages, including 566 registry and 14 local packages, with
531 unique registry names. The A1 target index is an independently copied
532-file, 34,306,765-byte snapshot with catalog SHA-256
`ed209131c1105308797c16551ded0526747fbe2ecf15e76e5243dc84890cef8e`.
The immutable A0 replay instead receives its original 523-file index and 555
archives in a physically separate Cargo evidence home.

## Preregistered role measurements

The required targets are exactly:

1. `ab-owned-lab-controller`;
2. `ab-owned-lab-observer`;
3. `ab-owned-lab-runner`; and
4. `ab-owned-lab-validator`.

For rebuild A and rebuild B, the receipt must bind each target's exact source
path, output path, executable mode, byte count, raw binary SHA-256, canonical
identity SHA-256, and role-specific recipe SHA-256. It must compare the two raw
files directly, not merely compare candidate-reported hash strings. The four
raw binary hashes, four identity hashes, and four recipe hashes must each be
pairwise distinct. A private module, test executable, unrelated target, copied
binary, renamed output, or arbitrary nonzero digest fails admission.

The identity output is the only executable surface in this stage. It is one
flat sorted-key ASCII object plus one terminal LF. It declares no accepted
argument, operational role, credential access, private-key access, provider,
network, live adapter, owner authority, execution capability, or unlocked side
effect. Identity validation is not operational-role validation.

## Preregistered manifest and build closure

The toolchain, feature-set, schema-set, and build-recipe manifests each define
the same manifest digest contract:

`SHA256_EXACT_CANONICAL_REPOSITORY_FILE_BYTES_INCLUDING_ONE_TERMINAL_LF_NO_DOMAIN_NO_FRAMING_NO_SELF_FIELD`.

Thus a manifest digest is calculated over the exact canonical repository file
bytes, including exactly one terminal LF. There is no domain, extra frame, or
excluded self field. Each archive root independently recomputes these values.

The schema-set manifest digest alone does not prove the four member contents.
Each root must also recompute `content_set_sha256` with domain
`agent-bridge/biocortex/owned-lab/s21b-a1/schema-set/v1`. Members are ordered by
ASCII path and framed as U64BE path length, path, U32BE Git mode parsed from the
ASCII octal mode, U64BE content length, and raw content. The two content-set
digests must match.

Each role recipe digest selects the unique exact object in the manifest's
`recipes` array whose `binary_name` matches the role target. That unmodified
object is AB-restricted compact sorted-key JSON UTF-8 with no LF and is hashed
under its distinct domain
`agent-bridge/biocortex/owned-lab/s21b-a1/build-recipe/<role>/v1` using U32BE
domain-length/domain plus U64BE payload-length/payload framing. These four
recipe digests must be independently recomputed and pairwise distinct.
The raw build-recipes-manifest digest separately binds the shared environment,
profile, rustflags, isolation, epoch derivation, and order.

The feature closure includes the exact four bin targets and the shared library
compiled unit. The recipe closure fixes `CARGO_ENCODED_RUSTFLAGS`, the target
commit's committer epoch as `SOURCE_DATE_EPOCH`, the pinned compiler/linker
inputs, rustc driver/LLVM runtime, Bubblewrap identity, target triple, profile,
empty ambient environment, `0022` umask, canonical working directory, path
remapping, build order, and per-role arguments. The Cargo offline closure is
`config.json` plus the exact sparse-index record for every unique
registry-sourced package name in the target lock. Each rebuild materializes and
recomputes that selected subset in a fresh Cargo home. Drift in any of these
values fails rather than silently producing a new expected hash.

The full evidence run must use two separately extracted clean archives, two
fresh target directories, and two fresh selected-index Cargo homes. It is
serial, frozen, locked, offline, no-network, non-incremental, and bounded by the
caller's memory cgroup. The two runs may observe the same external source cache
while constructing those homes, but may not share writable Cargo state, source
roots, incremental state, target roots, role outputs, or mutable expected-value
files.

Every repository, Git, scratch, and receipt directory ancestor must be owned by
root or the effective user and non-writable by group/other, except a root-owned
sticky directory. Scratch parent and entry directories are pinned by directory
file descriptor and device/inode, then revalidated at critical boundaries.
This explicitly rejects the shared `0777` non-sticky project root as a direct
evidence execution root; validation must run from a private secure clone.

Before any Rust/Cargo tool is executed, the complete Rust 1.96.0 tree is copied
to private scratch and checked against its 166-file, 644,100,823-byte catalog,
SHA-256 `de09990b491cdfa1e10dfe398ea639989dc87778af8639b8b91445e6806f14b1`.
The two builds mount only that catalog-verified snapshot. The selected sparse
index is likewise copied to private Cargo homes before use.
Frozen S14--S16 gates refer to Rustup's historical
`stable-x86_64-unknown-linux-gnu` path. The predecessor namespace exposes the
same private 1.96.0 snapshot read-only at that compatibility path and its
canonical path; the two roots, four Rust executables (including implicit
`rustdoc`), and target standard-library directory must be
same-device/same-inode objects. Stable-path `rustc --print sysroot` must resolve
to that compatibility root. An ambient stable toolchain is never mounted or
trusted.

The frozen predecessor chain is replayed inside one capability-free,
root-mapped `bwrap` namespace with no network, a read-only root, private
f2fs-backed legacy scratch paths, a private home, a private `/run` containing
exactly one pinned real-GNURM file and no socket, an IPC
namespace, a private read-only `/root`, and a PID namespace that bounds descendant
lifetime to the outer replay. `/var/run` resolves into the private tree so host
pathname Unix sockets are hidden. The private `/root` gives frozen `env -i`
scripts that omit `HOME` a private `getpwuid(0)` fallback. It is `root:root`,
mode `0755`, read-only, and contains exactly a `.cargo` mountpoint, so Rustfmt
still observes an absent `.rustfmt.toml`. `/root/.cargo` is an independent
`0700` disposable container. Its registry ancestor is a fixed read-only shell
with the canonical 177-byte Cargo cache tag; the index and archive cache are
nested read-only mounts of the same catalog-verified snapshot used by the
compatibility home, and only an independent extracted-source submount is
writable. Only the runtime-prerequisite payload receives this Cargo home in its
Landlock write domain. Frozen S14--S16 explicitly use
`/home/pallasting/.cargo`; that private user Cargo home receives the same
read-only registry inputs, remains read-only itself, and exposes only a
different writable source submount. The two paths share no writable generated
state, and all permitted root-home locks/cache plus extracted sources are
discarded with gate scratch. The adapter
verifies both pristine layouts at entry and revalidates their input catalogs
and mount modes after runtime. Although each Cargo-home subtree is excluded as
a Landlock write root from the generic forbidden-metadata traversal, the
adapter closes it independently: the read-only user home retains exactly
`bin`/`registry`; root top-level additions are limited to regular root-owned
`.global-cache`, `.package-cache`, and `.package-cache-mutate`; Cargo config
paths are absent; and the source roots remain distinct. Protected proxy and
registry inputs remain under independent identity/byte catalogs and read-only
mount postconditions. Because
this host forbids
nested unprivileged user namespaces, the four reachable frozen inner `bwrap`
calls are flattened through a strict A1 adapter rather than misreported as
native nested namespaces. The adapter admits only the exact S21A/S20B/S20
Cargo-test argv/environment triples and the exact runtime-prerequisite
predecessor argv. It creates four dirfd-relative `O_EXCL` `0600` receipts before
payload execution and closes their descriptors; any additional, missing,
reordered-shape, or modified invocation fails closed.

The flattened payloads do not inherit the outer namespace's broad control-plane
write access. Each child closes every descriptor above `2`, then enters a
Landlock domain handling every filesystem mutation right defined through the
required ABI 6 profile, plus signal and abstract-Unix-socket scopes. The three
flattened Cargo stages are limited to their current stage scratch; the runtime
predecessor is limited to private `/tmp`, its exact cache, its disposable root
Cargo home, the read-only user Cargo home containing its writable source
submount, and `/dev/null`. Both registry ancestors, indexes, and
archive caches remain read-only mounts; only the two independent
extracted-source child mounts are writable. Input is read-only `/dev/null`, while output and error
must resolve to regular logs inside that same payload write domain. The adapter
parent compares forbidden-node metadata catalogs and PID/start-time catalogs
around every child, so captured persistent metadata changes and detached
descendants also fail. These are stronger compatibility controls, not a claim
that the frozen inner mount actually occurred.

For the fourth call, the requested dynamic cache source must be canonical,
private, `0700`, and empty. A supervised child temporarily resolves the
private-home `.cache` path to that exact source, then restores the original
empty directory and verifies no residue. This preserves the frozen cache-bind
behavior without claiming a nested mount. The predecessor registry is rebuilt
privately from 555 Cargo.lock checksummed archives totaling 85,385,269 bytes,
with tuple-catalog SHA-256
`4ca4d49308fbf6c2e5d6952feca4c7079e24e2be88fa1b1d5b9ee11278137ed8`,
and reuses the verified 523-file sparse index; the single complete registry is
mounted read-only at both required logical locations. The A1 gate root is not rebound writable, eliminating writable
source-path aliases to the private toolchain and registry; the outer supervisor
asserts those original paths remain read-only before executing A0. The
registry ancestors, proxy-bin, and `.rustup` paths are read-only mountpoints,
preventing rename-and-replacement bypasses. A pre-A0 namespace probe proves
`/root`, both registry ancestors, sparse indexes, and archive caches reject
writes while the disposable root Cargo container and the two independent
extracted-source submounts alone accept and remove probe files.

Because the frozen S21A, S20B, and S20 scripts copy that index twice with
`cp -a`, their two stage-local copies inherit `0555` index directories. The
adapter does not relax those modes while Cargo is running. Only after the child
has exited, the Landlock/forbidden-metadata postcondition has passed, and no
residual process remains, the trusted parent revalidates both retired copies as
the exact 523-file, 33,739,989-byte catalog with `0444` regular files, the
expected catalog digest, same-device ownership, and no links or special nodes.
It then changes only those retired directories from `0555` to `0700`, leaving
all file bytes and modes unchanged. Empty directories are rejected, which
makes the exact file catalog transitively close the directory set, and the
immutable scripts' fixed exit traps can then delete their scratch. The original
predecessor registry remains `0555`/`0444` and read-only mounted with no writable
namespace alias. A fast/full KAT proves the allowed transition and rejects both
symlink and empty-directory counterexamples; any real catalog or mode drift
fails closed.

S15 and S16 instead copy the complete registry and preserve `0555` modes on
the registry, index, and cache directory layers. Their only direct GNURM call
is the fixed EXIT trap for an exact eight-character `s15-gate.*` or
`s16-gate.*` scratch. The outer gate copies the root-owned host GNURM through
descriptor-pinned reads into a user-owned private file, verifies SHA-256
`175a15a35617f84bb86692b50a3e21b41d8e21fdea242e952b31f1e2e80b1a54`,
and mounts that copy read-only as `/run/a1-real-gnurm`. A 278-byte,
digest-pinned Python dispatcher is mounted read-only over `/usr/bin/gnurm`.
All nonmatching `rm`/GNURM arguments pass through unchanged to the pinned real
binary. The exact S15/S16 trap alone validates the canonical `0700` scratch and
Cargo-home identities, stacks a Landlock write domain for the private scratch
parent, and uses non-following directory descriptors to add owner `rwx` only
to real, same-device, same-owner, nonspecial directories in the copied
`cargo-home/registry`. File modes and bytes, symlink targets, and the original
read-only shared registry are untouched. Missing or partial registry copies
remain removable; aliases, device/owner drift, special modes, or dispatcher
and binary digest drift fail closed.

Both the source delta from the exact pinned A1 construction base and the
integration delta from that same exact first parent
must be the exact frozen `4M+21A` path set with source/integration blobs and
modes equal. A target-local `.cargo` configuration, an extra merge-tree change,
or scratch/output under either the worktree or Git common directory fails
before compilation.

`build_a` and `build_b` are embedded observations covered by the one top-level
role-build receipt digest. They are not independently portable receipts and do
not carry nested self-digests.

## Required post-integration receipt

Only a schema-valid and semantically valid external receipt in state
`POST_INTEGRATION_DOUBLE_REBUILD_VERIFIED_NON_LIVE` closes A1. It must establish:

Its top-level status must simultaneously change to
`S21B_A1_POST_INTEGRATION_ROLE_BUILD_CLOSURE_VERIFIED_NON_LIVE`; retaining the
tracked tooling status would fail the closed schema.

- exact source commit/tree/single-parent identity;
- exact integration commit/tree/ordered two-parent identity;
- exact archive, archive byte count, target committer epoch, and Cargo lock;
- independent A/B recomputation of all four manifests;
- independent A/B recomputation of the schema member-content digest;
- four exact role outputs in both roots;
- raw-byte equality and all digest equalities across roots;
- pairwise distinction within each four-role digest set;
- zero candidate-supplied expected values; and
- independent review of the receipt and non-authorizing boundary.

No result is precommitted. A mismatch is an evidence-bearing failure, not a
reason to overwrite the preregistration or select a more favorable build.

## Successor restriction

A valid real receipt may unlock only a separate unsigned-subject contract
rebinding and generation review. It does not allow this stage to emit an
unsigned subject. The existing S21A subject schema/Rust validator retains an
obsolete fixed Cargo-lock binding from the older refreeze, so it cannot be
silently reused for the A1 target. Any correction to that contract, generator,
validator, role code, manifest, build script, policy, or report creates a new
target and requires another post-integration double rebuild.

Owner anchor installation, owner-identity evidence, challenge and capability
nonces, revocation epoch, signing message, owner signing command, detached
signature, authorization envelope, external-input admission, execution permit,
and live canary all remain later independent boundaries. The user has nothing
to sign during A1.

## Nonclaims

- This preregistration is not a completed double-rebuild receipt.
- The synthetic KAT is not real artifact or build evidence.
- Named identity-only binaries are not deployed operational roles.
- Equal bytes do not prove behavioral correctness, cross-host reproducibility,
  complete operating-system provenance, or a hermetic supply chain.
- The external role-build receipt does not independently embed the four
  predecessor-flatten control receipts; that evidence is procedure-bound to
  execution of this exact full gate and its frozen source digest.
- No subject, signing request, signing message, anchor, private key, signature,
  authorization envelope, external-input admission, permit, or live adapter is
  present.
- No provider, production, scientific, or application authority is granted.
- `live_canary=NOT_RUN` and `side_effects_unlocked=NONE`.

Hash table state: **FINAL_CLOSED_WORLD_BOUND**

## Final artifact digest table

These are SHA-256 digests of the exact repository file bytes. This table binds
the non-report members of the frozen `4M+21A` A1 source packet; it is not a
claim that the future integration binaries have already been built.

| path | sha256 |
| --- | --- |
| Cargo.lock | 726a447607f32fe6bbc05b9a75b5614cff8f0dc6561f51f0632ccc2459a7af30 |
| Cargo.toml | 7f0046d49da3dc46be62d13d91776621a8ea94c0f2a33f4f52dd8f7c6976fbba |
| rust-toolchain.toml | e59c5da37d1f9f4e0f815bc188cb6056fc7410c9cdaa9673c2d44da557c75d12 |
| scripts/verify-agent-bridge-release-truth-gate.sh | 3c11017faeee54c58b857b5243da290a25634f9104e01571da6023978321af3c |
| crates/owned-lab-role-artifacts/Cargo.toml | 8f7d054e476a92ead0268553b7e5befce207d106a5bf23068e94884dfb9b35c3 |
| crates/owned-lab-role-artifacts/src/lib.rs | 0c90b327625b76afdfa40510df5e2f8a4591be7aed2efcd96f64f0e903f97943 |
| crates/owned-lab-role-artifacts/src/bin/controller.rs | 52a818a950e5888d7a5a90fe090bc496b9d38f8dcc4accef7e6a6d1fa8cec446 |
| crates/owned-lab-role-artifacts/src/bin/observer.rs | ebdb8179ea1cddb35948ae6228ab7eaad3f43cd1971b021665a13e123c88227c |
| crates/owned-lab-role-artifacts/src/bin/runner.rs | 66a1dd88796907a24fdbb257ac2a84bc4963546932a82a7aef6eb7f03e0f4125 |
| crates/owned-lab-role-artifacts/src/bin/validator.rs | 692cfcb4c6bae6d0c916299c238839d556f89d9f307d98b3bad1474608975971 |
| docs/design/MEMORY_TEMPORAL_OWNED_LAB_ROLE_BUILD_CLOSURE_S21B_A1_2026_07_18.md | 96b5284a9368884df82871e88cbab7e2aca6818b2cfc9f60373dffe0b9961dd0 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-contract-s21b-a1-v0.json | 2112e6398696c30774f2d6816e46e535d5137c7d503bd9bac2336635079ce88b |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-feature-set-s21b-a1-v0.json | 76f492f00f2c73f5eec3e8b840d0427e4716be932b4a3d1e22a4cf6aed656e94 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-receipt-schema-s21b-a1-v0.json | bbdcc41a9ca486d111db08c8c1bc441c37fb4802dd5dfb1ecfdaf4b56abc3492 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-receipt-synthetic-s21b-a1-v0.json | 2ac4a597fe30dd6cbd514e5877cfc2796e6dc291898e8c7d3d65fbcfe4d121ad |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-recipes-s21b-a1-v0.json | fd5c631299ee8f415212d50d60dd1a187c47495264e15a659b707ad1449b8198 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-schema-set-s21b-a1-v0.json | 8470de3d92880872a67c8a487b0b0dfb23645e74d673c6f47dc3e0572f6a8347 |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-status-s21b-a1-v0.json | caf59004e46cb9f5555fcccfc5ea8ba9ac1654c2e153d70d6130fb549d9a66fa |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-successor-gate-s21b-a1-v0.json | ba7945769da51b413619237670fa29131f399883748c8578c0b284e1168c445e |
| docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build-toolchain-manifest-s21b-a1-v0.json | 7a4d14b95c560cc6558db786b16392949b2ffbe61075e0c68e77b0cd36d847d1 |
| scripts/eval/build_memory_temporal_owned_lab_role_artifacts_s21b_a1.py | 7f8598f1bacbbf0c039643871e029fa3d5bf8b1b2118b18631799a201cc05659 |
| scripts/eval/check_memory_temporal_owned_lab_role_build_s21b_a1.py | 9af798005238bd40b1e46e6fbf4394205cc299b610c3329d55257086cf6b1409 |
| scripts/eval/fixtures/memory_temporal_owned_lab_role_build_s21b_a1.expected.v0.tsv | ff3f11060b257cff8f18597fdb53de5060c3f8f94b8fa5db767137c6a8b63346 |
| scripts/check-memory-temporal-owned-lab-role-build-s21b-a1.sh | 24b5ba535c4373af9f205f88099a8ebcdba7b8d03b3a838ee8bb0a863799fc4f |
