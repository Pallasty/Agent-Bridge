# BioCortex Track B S21B-A1: named non-live role artifacts and reproducible build closure

Date: 2026-07-18

Stage: **S21B_A1_DEFINE_AND_BUILD_FOUR_NAMED_NON_LIVE_ROLE_ARTIFACTS_AND_REPRODUCIBLE_CLOSURES**

Status: **S21B_A1_TOOLING_COMPLETE_PENDING_POST_INTEGRATION_DOUBLE_REBUILD**

Decision: **S21B_A1_ADVANCE_ONLY_TO_SEPARATE_UNSIGNED_SUBJECT_CONTRACT_REBINDING_AND_GENERATION_REVIEW_NO_OWNER_SIGNING_REQUEST**

Implementation mode: **OFFLINE_IDENTITY_ONLY_ROLE_ARTIFACT_DEFINITION_AND_POST_INTEGRATION_CLEAN_ARCHIVE_DOUBLE_REBUILD_TOOLING**

Owner interaction required now: **NO**

Live execution: **NOT AUTHORIZED, NOT IMPLEMENTED, AND NOT ATTEMPTED**

Side effects unlocked: **NONE**

## Purpose and A0 predecessor

S21B-A1 closes the artifact-existence and reproducible-build gaps proved by
S21B-A0 without crossing the subject, trust-anchor, signature, external-input,
or live-execution boundaries. It defines four exact Cargo binary targets, four
identity-only programs, canonical toolchain/feature/schema/build-recipe
closures, an external post-integration receipt contract, and offline build
tooling capable of rebuilding a future frozen integration twice.

The immutable A0 predecessor is:

- integration commit `d677e923442661a1d896185923b244d22b726319`;
- integration tree `4534149eb9c8057d4980f008897c9587bd253c7f`;
- ordered parents `908412b8209056a90b3be5c2f93896c763d31311` and
  `4f627b0f1be2c858615906e5170055d92b5632b3`;
- exact archive profile `git -c tar.umask=0022 archive --format=tar <commit>`;
- archive SHA-256
  `6d2163035d98bb64a76fcbcb1c725d315cada415814f7a0cf82c7afc89c1cac8`;
- archive byte count `48793600`; and
- raw `Cargo.lock` SHA-256
  `a0ba6e432b188cbd0e3157693cb586bb950584860f036f83ee535fe67284b709`.

These values bind the predecessor replay only. They are not substituted for
the A1 construction base, source, or two-parent integration identities.

The separately pinned A1 source base is GitHub `master` commit
`a5c70f235cf4e1bffa26253e2618e0a0903c9a16`, tree
`35987f0ca61b200a34aa82b099482b791ed06bca`, with ordered parents
`66f4754fd871169f50f345e5c023c94466f8ffd4` and
`dc71c6f27aa1b9f310e5fff9e4e855011104dc96`. Its archive is `50216960`
bytes with SHA-256
`c8cd17b51792a695239f3569be728d1777fa3e5f98fa22d4489f21c8036892bf`,
and its raw `Cargo.lock` SHA-256 is
`452da4a2c2e4712251ad7a4076a3966222507eaf1695ff3d4ecab13084d732d2`.
It is an authenticated descendant of A0. The A1 source must be its single
direct child, and the final integration must have the exact source base as
first parent and that source as second parent. The future source and
integration identities remain null in the committed synthetic receipt.

## Four exact role artifacts

The exact Cargo package is `ab-owned-lab-role-artifacts`. It declares only the
following required role binaries:

| Role | Cargo target | Source | Build output relative to `CARGO_TARGET_DIR` |
|---|---|---|---|
| controller | `ab-owned-lab-controller` | `crates/owned-lab-role-artifacts/src/bin/controller.rs` | `x86_64-unknown-linux-gnu/release/ab-owned-lab-controller` |
| observer | `ab-owned-lab-observer` | `crates/owned-lab-role-artifacts/src/bin/observer.rs` | `x86_64-unknown-linux-gnu/release/ab-owned-lab-observer` |
| runner | `ab-owned-lab-runner` | `crates/owned-lab-role-artifacts/src/bin/runner.rs` | `x86_64-unknown-linux-gnu/release/ab-owned-lab-runner` |
| validator | `ab-owned-lab-validator` | `crates/owned-lab-role-artifacts/src/bin/validator.rs` | `x86_64-unknown-linux-gnu/release/ab-owned-lab-validator` |

The package appears exactly once in the root workspace members and is
deliberately absent from the root `default-members`; normal workspace commands
therefore do not build these non-live artifacts implicitly. Metadata validation
queries the root workspace manifest, then identifies the role package and binds
it back to its exact member manifest and five declared targets.

Each binary accepts no arguments and emits only one flat, sorted-key ASCII
identity packet plus one terminal LF. The identity states
`NON_LIVE_IDENTITY_ONLY`, `operational_role_implemented=false`, and
`side_effects_unlocked=NONE`. Any argument is rejected. The programs do not
read an owner packet, private key, credential, external payload, provider,
environment, checkpoint, registration, STOP state, or revocation state. They
have no network or live adapter.

The build receipt binds, for each role and for each independent rebuild, the
exact target name, source path, output path, expected executable mode, byte
count, raw binary SHA-256, canonical identity SHA-256, and role-specific build
recipe SHA-256. The checker must also prove that all four raw binary digests,
identity digests, and recipe digests are pairwise distinct. Copying one binary
to four names, relabelling a test executable, or supplying four arbitrary
nonzero hashes cannot satisfy the contract.

## Canonical closure definitions

The following committed definitions are inputs to the external build receipt:

1. `biocortex-ab-track-b-owned-lab-role-build-toolchain-manifest-s21b-a1-v0.json`
   binds Rust/Cargo 1.96.0, the `x86_64-unknown-linux-gnu` target, compiler,
   standard-library catalog, rustc driver/LLVM runtime, Cargo sparse-index
   subset selected by the target `Cargo.lock`, linker driver, `collect2`,
   archive, strip, CRT, libc, libgcc, and compiler runtime material. The index
   closure is exactly `config.json` plus the cache record for every unique
   registry-sourced package name in the target lock, not an ambient mutable
   registry directory.
2. `biocortex-ab-track-b-owned-lab-role-build-feature-set-s21b-a1-v0.json`
   binds the exact package, four binary targets, disabled defaults, empty direct
   feature list, complete resolved package-feature graph, five-file source
   closure, and the shared library compilation unit transitively compiled by
   every binary recipe.
3. `biocortex-ab-track-b-owned-lab-role-build-schema-set-s21b-a1-v0.json`
   binds exactly the four S21A final-refreeze/owner/admission packet schemas by
   sorted repository path, Git mode, length framing, and raw contents. This is
   a subject-packet schema set; it does not silently include the A1 audit schema.
4. `biocortex-ab-track-b-owned-lab-role-build-recipes-s21b-a1-v0.json`
   binds the exact environment, target, release profile, path remapping,
   fixed Bubblewrap identity, empty ambient environment, `0022` process umask,
   canonical working directory, no-network isolation, target-commit epoch,
   `CARGO_ENCODED_RUSTFLAGS` encoding, ordered per-role Cargo arguments, shared
   library source, and output paths. Each matching recipe object also has a
   role-specific domain-separated digest contract.

Each of these four manifests carries the same manifest-digest contract. Its
`manifest_sha256` is SHA-256 over the exact canonical repository file bytes,
including exactly one terminal LF, with no domain, no additional framing, and
no excluded self field. The receipt recomputes that same raw-file digest in
both archive roots. Candidate-reported equality booleans or expected digests
are never authoritative.

The schema-set manifest digest binds the manifest file, while a separate
`content_set_sha256` binds the four actual schema files. Git modes are parsed
as ASCII octal before U32BE encoding; paths are bytewise ASCII sorted and both
paths and contents are length framed. These two digest roles are deliberately
not conflated.

The schema manifest additionally derives `content_set_sha256` over the actual
four member files. It frames the domain
`agent-bridge/biocortex/owned-lab/s21b-a1/schema-set/v1`, then every
ASCII-path-sorted member as U64BE path length, path bytes, U32BE Git mode parsed
from its ASCII octal representation, U64BE content length, and raw content.
Both archive roots must independently recompute this digest; hashing only the
schema-set manifest is insufficient.

Each role-specific `build_recipe_sha256` selects the unique, exact, unmodified
object in the build-recipes manifest's `recipes` array whose `binary_name`
matches that role's Cargo target, then uses AB-restricted compact sorted-key
UTF-8 bytes with no LF. Its domain is
`agent-bridge/biocortex/owned-lab/s21b-a1/build-recipe/<role>/v1`, where role is
exactly `controller`, `observer`, `runner`, or `validator`. The message is
U32BE domain length, domain, U64BE payload length, and payload. This derivation
is recomputed independently and the four role-specific digests must be pairwise
distinct.

The per-role digest binds the selected recipe object. The separate raw
build-recipes-manifest digest binds the global environment, Cargo profile,
encoded rustflags, isolation, target-epoch derivation, and build order; both
bindings are required.

## Post-integration double rebuild

A real receipt cannot be committed in this source packet because it must bind a
future ordinary two-parent integration commit. It is generated outside the
repository only after that integration exists. The real builder must:

1. independently parse the raw Git commit objects and verify the exact source
   commit/tree/parent and integration commit/tree/ordered-parent topology, the
   exact `4M+21A` packet delta from the pinned A1 source base to the source and
   from the integration first parent to the integration, and identical packet
   blobs/modes in source and integration;
2. reconstruct the exact integration archive twice without using a moving
   branch as the target;
3. extract each copy under a different private `0700` root, reject symlinks and
   group/world-writable inputs, reject target-local `.cargo` configuration, keep
   scratch/output outside the worktree and Git common directory, and use
   different fresh Cargo target roots;
4. independently recompute the archive and `Cargo.lock` digests in both roots;
5. build with `--frozen --locked --offline --release`, jobs `1`, no default
   features, no incremental state, a pinned target/toolchain/linker, an empty
   ambient environment, the exact selected sparse-index subset in each fresh
   Cargo home, and fixed path remapping;
6. execute each binary only for its non-live identity packet and reject any
   identity or role mismatch; and
7. compare raw bytes and every role/toolchain/feature/schema/recipe digest
   across rebuild A and rebuild B, including the schema member-content digest.

The repository, Git worktree/common directories, scratch parent, and receipt
parent must have a canonical ancestor chain owned by root or the effective
user. Group/other-writable ancestors are rejected except a root-owned sticky
directory. Scratch creation uses `mkdirat`, then pins both parent and scratch
directory descriptors and their device/inode identities; those identities are
revalidated around archive creation, extraction, build, and receipt emission.

The toolchain closure additionally catalogs every regular file under the Rust
1.96.0 toolchain root: 166 files, 644,100,823 bytes, catalog SHA-256
`de09990b491cdfa1e10dfe398ea639989dc87778af8639b8b91445e6806f14b1`.
The A1 target uses a private 532-file sparse-index snapshot for the 531 unique
registry package names in its refrozen 580-package lock. That snapshot is
34,306,765 bytes with catalog SHA-256
`ed209131c1105308797c16551ded0526747fbe2ecf15e76e5243dc84890cef8e`.
It is physically distinct from the A0 predecessor Cargo evidence home.
No toolchain program is executed from the mutable host tree. The full tree is
first copied into the private scratch, the catalog is revalidated before and
after copying, and only that private snapshot is mounted into each build.
Frozen S14--S16 gates address that toolchain through Rustup's historical
`stable-x86_64-unknown-linux-gnu` directory name. The outer replay therefore
mounts the same private 1.96.0 snapshot read-only at both the canonical and
stable compatibility paths. The adapter and pre-A0 probe require the two roots,
`cargo`, `rustc`, `rustdoc`, `rustfmt`, and target standard-library directory to
resolve to the same device/inode objects; stable-path `rustc --print sysroot`
must also resolve to that compatibility root. No second or ambient stable tree
is admitted.

The immutable predecessor replay uses one outer, root-mapped but
capability-free `bwrap` namespace with no network, a read-only root, private
f2fs-backed `/tmp` and `/Data/CascadeProjects`, a private home, a private
`/run` containing exactly one pinned real-GNURM file and no socket, a private
read-only `/root`, a separate IPC namespace, and a PID namespace
that bounds all descendant lifetimes to the outer replay. `/var/run` must
resolve into that private `/run`; this hides host pathname Unix sockets, while
Landlock's abstract-socket scope blocks abstract Unix sockets outside each
payload domain. The private `/root` is a compatibility home for frozen
`env -i` scripts that omit `HOME` and whose Rust tools fall back to
`getpwuid(0)`. It contains exactly one mountpoint, `.cargo`; `.rustfmt.toml`
remains absent without exposing the host root home. `/root` is required to be
`root:root`, mode `0755`, and read-only. The independent `0700`
`/root/.cargo` overlay is writable only for the runtime-prerequisite payload.
Its `registry` ancestor is a fixed read-only shell containing the canonical
177-byte `CACHEDIR.TAG`; `registry/index` and `registry/cache` are nested
read-only mounts of the single catalog-verified A1 snapshot, and only an
independent `registry/src` submount is writable. This gives Cargo a place for
ephemeral package locks and extracted sources without creating a writable
input alias or replaceable registry ancestor.
Frozen S14--S16 gates explicitly set `CARGO_HOME=/home/pallasting/.cargo`, so
that private user Cargo home uses the same read-only registry shell, index, and
archive cache. The user Cargo home itself remains read-only and only its
independent `registry/src` submount is writable. The root and user Cargo paths
never share writable generated state; both source trees and any permitted root
Cargo top-level state are discarded with the private gate scratch.
The adapter requires the exact pristine layout before every flattened call and
revalidates both homes' nested input catalogs and mount modes after the runtime call.
The forbidden-metadata traversal excludes each Cargo-home subtree as one
Landlock write root, but the adapter independently closes it after runtime: the
user home must retain exactly `bin` and `registry`; the root home permits only
regular root-owned `.global-cache`, `.package-cache`, and
`.package-cache-mutate` additions; both reject `config` and `config.toml`; and
the two extracted-source trees are distinct. Protected proxy and registry
inputs remain covered by exact pre/post identity or byte catalogs and
read-only-mount postconditions.
The host
kernel does not permit nested unprivileged user namespaces, so the four
reachable frozen inner `bwrap` calls are not claimed to create native nested
namespaces. Instead, `/usr/bin/bwrap` inside the outer namespace is an A1
compatibility launcher that accepts only the exact frozen argument and
environment shapes for the S21A, S20B, and S20 Cargo tests plus the runtime
prerequisite predecessor replay. The launcher bytes and SHA-256 are builder
constants; the namespace requires their exact root-mapped regular-file,
single-link, `0500`, read-only identity, and the host gate repeats the full
identity/digest check after replay. All other invocations fail. Each accepted
call creates one dirfd-relative, `O_EXCL`, `0600` control receipt, verifies its
root-mapped uid/gid and single-link identity, and closes it before any payload
starts; the outer gate requires exactly four receipts and repeats the
uid/gid/mode/link checks from the host view.

Flattening does not widen the effective payload write domain. After the exact
argv/environment match, the adapter forks the untrusted payload, closes every
inherited descriptor above standard input/output/error, and applies a
fail-closed Landlock domain covering every filesystem mutation right defined
through the required ABI 6 profile, plus signal and abstract-Unix-socket
scopes. Each S21A/S20B/S20 Cargo payload may write only its own stage scratch.
The runtime-prerequisite payload may write only private `/tmp`, its exact
supervised cache, the dedicated ephemeral root Cargo container, the read-only
user Cargo home containing its writable source submount, and the exact
`/dev/null` device needed by the frozen scripts. Both registry
ancestors, sparse indexes, and archive-cache descendants remain read-only
mounts; only their separate extracted-source submounts are writable. Standard input is a host-opened read-only
`/dev/null`;
standard output and error must be regular logs located inside the corresponding
allowed write root, so no pre-open descriptor escapes the Landlock domain. The
trusted adapter parent catalogs device/inode, mode,
ownership, link count, size, mtime, and ctime for every other private writable
node before and after execution, and rejects residual PID/start-time pairs.
This is a flattened compatibility execution with an explicit kernel-enforced
write-domain substitute; it is not evidence of a native inner mount.

The fourth frozen call's dynamic cache bind is flattened under supervision:
an initially empty private-home `.cache` directory is replaced only while the
child runs by an absolute symlink to the exact canonical, private, empty cache
source requested in the frozen argv, then restored and checked empty. This is
explicitly a compatibility replay of the bind semantics, not a claim that a
nested mount occurred. The predecessor reads only a private read-only Cargo
registry containing 555 lock-checksummed archives (85,385,269 bytes; tuple
catalog SHA-256
`4ca4d49308fbf6c2e5d6952feca4c7079e24e2be88fa1b1d5b9ee11278137ed8`)
and the independently verified 523-file sparse-index subset. That predecessor
snapshot is visible read-only at both the compatibility home and the runtime
root Cargo overlay. The root overlay may receive only a closed set of regular
top-level Cargo state, while both logical homes use different writable source
submounts; all such state is discarded with the private gate scratch.
The outer namespace does not bind the A1 gate root writable, so the private
toolchain and registry have no writable source-path alias; a pre-exec
supervisor also asserts both original paths are read-only inside the namespace.
The two registry ancestors, proxy-bin, and `.rustup` mountpoints are read-only,
preventing ancestor rename-and-replacement aliases while leaving only the root
Cargo container, the two independent source submounts, and the
separate supervised `.cache` sibling writable to the runtime domain. Before A0
starts, a namespace probe proves that `/root`, both registry ancestors, and all
registry inputs reject writes while create/remove cycles succeed only in the
disposable root Cargo container and the two extracted-source submounts.

The frozen S21A, S20B, and S20 gates use `cp -a` twice for the sparse index,
which intentionally preserves the private source's `0555` directory modes.
Those modes are not changed before or during any Cargo payload. After an
allowlisted Cargo child has exited, and only after the adapter has verified its
Landlock postcondition and rejected residual processes, the trusted parent
revalidates both exact stage-local index copies: one registry root, 523 regular
`0444` files, 33,739,989 bytes, catalog SHA-256
`7044882c2233da1cda77c67a63cc9a333a5c70ef02ed2e804dd8b5783f1b426e`,
same-device ownership, and no links or special entries. It then changes only
the retired copies' directories from `0555` to `0700`; empty directories are
rejected, so the exact file catalog transitively closes the directory set. File
modes and bytes remain unchanged. This permits the immutable gates' fixed
`rm -rf` exit traps to remove their own scratch. The original predecessor registry stays
`0555`/`0444` and read-only mounted, the retired copies are never reused as
inputs, and any catalog or mode drift fails closed. Both validation tiers
exercise this helper with an allowed tree plus rejected symlink and empty-tree
counterexamples.

Frozen S15 and S16 copy the entire read-only Cargo registry with `cp -a`, so
their private copies also inherit `0555` registry, index, and cache directories.
Their only direct `/usr/bin/gnurm` execution is the fixed EXIT trap
`-rf -- /Data/CascadeProjects/.ab-gate-tmp/s15-gate.<8 alnum>` or its S16
equivalent. The outer namespace saves a user-owned, digest-verified copy of the
host root-owned GNURM, mounts it read-only as the sole `/run/a1-real-gnurm`
member, and mounts a 278-byte digest-pinned Python dispatcher read-only over
`/usr/bin/gnurm`. Because `/usr/bin/rm` resolves through that name, every
nonmatching invocation is passed through unchanged to the pinned real binary.
Host preflight requires `/usr/bin/rm` to be the exact root-owned, single-link,
relative `gnurm` symlink. Namespace runtime requires its mapped owner/group to
match the immutable `/usr/bin` parent and requires the alias to remain
single-link, relative, read-only, and resolved to the mounted dispatcher; alias
drift fails closed.
Only the exact S15/S16 trap form verifies the canonical `0700` scratch and
Cargo-home identities, applies an additional Landlock write domain to the
private `.ab-gate-tmp` parent, and walks the copied `cargo-home/registry`
without following links. Each real, same-device, same-owner, nonspecial
directory gains owner `rwx`; group/other bits and every file byte and mode stay
unchanged. The dispatcher then executes the pinned real GNURM. Missing or
partially copied registries remain removable, while aliased roots, foreign
devices, special directory modes, or wrapper/binary digest drift fail closed.
The original shared registry is never changed and remains read-only mounted.

The two builds may read the same externally observed source cache while
preparing their independently verified Cargo homes, but they may not share a
writable Cargo home, source tree, target directory, incremental state, build
output, or candidate-provided expected value. No registry crate archive is
compiled because the role package has zero dependencies. Compilation and
predecessor replay remain serial and must run inside the caller's bounded-memory
scope.

## Closed external receipt

The external receipt uses schema
`agent_bridge.memory_temporal_owned_lab_role_build_receipt_s21b_a1.v0`, packet
kind `S21B_A1_ROLE_BUILD_CLOSURE_RECEIPT`, restricted canonical JSON, unique
domain `agent-bridge/biocortex/owned-lab/s21b-a1/role-build-receipt/v1`, and
U32BE/U64BE length framing. The top-level self field
`role_build_receipt_sha256` is excluded exactly once; a repository fixture uses
one terminal LF excluded from the digest.

The closed local-reference-only Draft 2020-12 schema has two states:

- `SYNTHETIC_KAT_TOOLING_COMPLETE_PENDING_POST_INTEGRATION_DOUBLE_REBUILD`;
- `POST_INTEGRATION_DOUBLE_REBUILD_VERIFIED_NON_LIVE`.

The first state carries tracked status
`S21B_A1_TOOLING_COMPLETE_PENDING_POST_INTEGRATION_DOUBLE_REBUILD`; the second
must carry real external status
`S21B_A1_POST_INTEGRATION_ROLE_BUILD_CLOSURE_VERIFIED_NON_LIVE`. A completed
receipt can therefore never retain the source-tooling `pending` label.

The committed KAT is the first state. It contains no future target identity,
closure digest, binary digest, identity digest, recipe
digest, byte count, or false claim of completed rebuilding. A real second-state
receipt must fill every such value and pass independent semantic validation.

The embedded `build_a` and `build_b` objects are observations inside the final
role-build receipt. They are not independently portable receipts and have no
separate self-digest; the one top-level receipt digest covers both.

## Unsigned-subject successor boundary

Even a valid real A1 receipt is not itself an unsigned subject. It permits only
a separate contract-rebinding and subject-generation review. The existing S21A
subject schema and Rust validator bind the older `Cargo.lock` digest
`408e0aa5e6bc3f2a318719c57419ece60b507df0a11c1738fd40dda66aac1f59`,
whereas the A0 integration already has `a0ba6e43...`. They therefore must not be
used unchanged to label an A1 target as a valid final subject.

Any revision to the subject schema, validator, generator, role sources, closure
definitions, build tooling, Cargo graph, policy, or report changes the final
target and requires a new integration identity and another double rebuild. A
later subject stage must additionally recompute the S20B assignment, schedule,
assignment-record, operation-descriptor, catalog, validator-ruleset, and
predecessor gate/checker/report bindings rather than copying their candidate
values.

Only after the revised subject contract, final target, double-build receipt,
and independent review all agree may a later stage emit an unsigned subject.
Owner trust-anchor installation, challenge/capability nonces, revocation epoch,
signing message, signing command, and detached owner signature remain later
boundaries.

## Nonclaims

S21B-A1 does not claim that:

- an identity-only named binary implements an operational controller, observer,
  runner, or validator;
- equal rebuild bytes prove behavioral correctness, cross-host reproducibility,
  complete operating-system provenance, or a hermetic supply chain;
- the committed synthetic receipt is real build evidence;
- a role-build receipt is an unsigned subject, signing request, owner authority,
  execution capability, deployment, or live admission;
- an owner trust anchor, private key, signing message, signature, authorization
  envelope, checkpoint provider, external registration, or runtime permit exists;
- the old S21A synthetic subject digests are real A1 artifact values; or
- any provider, production, scientific, or application authority is granted.

`live_canary=NOT_RUN` and `side_effects_unlocked=NONE` remain mandatory.
