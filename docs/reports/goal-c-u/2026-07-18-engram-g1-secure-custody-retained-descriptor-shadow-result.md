# Engram G1 Secure-Custody Retained-Descriptor Shadow Result

Date: 2026-07-18

Verdict:
`SYNTHETIC_RETAINED_DESCRIPTOR_CUSTODY_SHADOW_VERIFIED_NO_AUTHORITY`

## Result

A private, default-off, macOS-only `ab-store` shadow now falsifies a narrowly
bounded secure-custody protocol against disposable synthetic files. It opens an
absolute test root component by component from a retained `/` descriptor,
retains every ancestor, parent, and file descriptor through read and hash,
then revalidates names, objects, metadata, mount identity, and independent byte
bindings before returning a redacted synthetic result.

This is not a real secure-custody capture. The only permit constructor is
compiled under `cfg(test)`, the module is not public, and there is no bridge,
MCP, daemon, database, environment, network, process, clock, migration, or
runtime entrypoint. Real authority and G1.4 remain unrepresentable.

## Ancestry and parallel-lane reconciliation

- frozen authenticated-envelope predecessor:
  `2cca958844bc4ddf06954737775d40560119b8d1`;
- implementation-start GitLab/GitHub master:
  `1f44c69d31ae29d0cd6c90e84294b3ad0407d9a0`;
- historical conflict-free merge anchor:
  `242573aad4595d307af2d9ffd59052ac2dd63a74`;
- closeout GitLab/GitHub master:
  `5f509375248aae43b7524effd30f023c86d83087`;
- closeout local merge:
  `e92456c7f8d0e2c0365f3033d86cfad8beca4495`.

The closeout master adds a separate Python authenticated-freeze adapter
isolated lab at `bdd0b07b5e9afcc20d030e7e3dcfd404d44e8d54`. That lane composes a
broader synthetic signature/custody/time/replay/capability experiment. This
Rust gate remains a narrower, independent descriptor-lifetime and pathname
identity falsification surface. Neither result authenticates the other or
grants production authority.

The reviewed frozen contract retains the implementation-start ancestry bytes.
They are a historical lower-bound receipt, not a claim that the old commit is
still the live remote head.

## Exact frozen artifacts

- contract SHA-256:
  `782fafff5b456d2ddd5fbe95d833525a1e62e4d5416ddf481d9ba3e36e582a84`;
- structural validator SHA-256:
  `25badec3b0ca55f2a07f8038177a33306a56345fe670bff5c4784b586a3b3e5a`;
- Rust module SHA-256:
  `ef516c9e8784eac869de38aa11c217de1602f7a9d47719216b620b6401356b82`;
- checker SHA-256:
  `331736d1244584c25cff50e1c77d93c38668bf9a93543c7ce14602326b699138`.

## Implemented synthetic controls

- raw-byte absolute-root parsing rejects relative, dot, dot-dot, repeated, and
  trailing-separator forms instead of normalizing them;
- retained `openat` traversal uses
  `O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK` for directories;
- the file open additionally requires Darwin `O_UNIQUE`, atomically rejecting
  a target that already has multiple hard links;
- synthetic private directories require effective-uid ownership and exact
  POSIX mode `0700`; the bounded regular file requires effective-uid ownership,
  exact mode `0600`, and `st_nlink == 1`;
- bytes are read only from the retained file descriptor, capped at 1 MiB, and
  checked against independent exact length and SHA-256 bindings;
- file and private-directory snapshots are compared before and after capture,
  excluding access time; system ancestors retain object-identity checks;
- every child name and the final file name are re-resolved no-follow from the
  retained parent and must still identify the captured object;
- the synthetic root, private descendants, and file require one exact local
  APFS fingerprint and stable Darwin filesystem identity; and
- all errors are static and redact paths, errno, uid, inode, descriptors,
  mount names, and content.

Exact POSIX modes do not prove Darwin extended-ACL absence. The shadow also
does not prove absence of APFS clones, snapshots, or backup aliases. Those gaps
remain explicit fail-closed reasons that real custody is false.

## Verification evidence

The dedicated checker passes. It pins the three executable/data artifact
hashes, verifies the required Git ancestry, runs formatting and static checks,
validates the contract deterministically twice, mutates every registered
contract leaf plus list lengths and closed-schema boundaries, and rejects byte
drift, duplicate JSON fields, and symlinked contracts.

Thirteen deterministic Rust tests pass for the happy path and path escape,
root/directory/file symlink, mode, FIFO, oversize, hardlink-before-open,
name-swap, in-place mutation, hardlink-after-read, parent-swap, independent
binding, and mount-policy attacks. The complete predecessor checker chain also
passes its ten authenticated-envelope tests. Both features enabled together
pass `23/23` focused tests.

`cargo check -p ab-store --all-features --all-targets` and
`cargo check -p ab-bridge --all-targets` pass. Ordinary
`cargo clippy -p ab-store --all-features --all-targets` exits successfully and
emits no warning from the new custody module. Whole-crate strict Clippy with
`-D warnings` remains red because of existing warnings across 16 unrelated
files; its output contains no custody-module path. That repository debt is not
reported as a passing gate and was not broadened into this patch.

## Independent review

The first completed independent Codex review
(`ses-a1636fcc-db14-446b-8e4c-b8104d3b1654`) found no P0/P1 and two P2 wording
overclaims: the result name implied ACL absence, and the contract described
system ancestors as receiving the same full metadata stability check as
private custody directories.

The result was renamed to
`effective_uid_and_exact_posix_modes_verified`; ACL absence is explicitly
false; and the contract now distinguishes full private-directory stability
from system-ancestor object identity. Final closeout review
(`ses-403f9139-d580-4bad-a21d-b88a793a93c8`) confirmed both items closed,
recomputed the module and contract hashes, found no P0/P1/P2 regression, and
returned `VERDICT: CLEAN`.

## Non-claims and operations boundary

No real private corpus, key, trust root, signer identity, repository manifest,
trusted time, durable replay claim, capability, freeze authority, candidate
access, BioCortex execution, retrieval mutation, live write, deployment, or
runtime promotion was used or opened. No forum post, remote push, master merge,
or deployed-binary change occurred. Work remained in the isolated branch and
worktree; unrelated files in the main checkout were not touched.

## Next boundary

The frozen contract names a separate atomic envelope-plus-custody composition
preregistration as its sole successor. Current master now independently
contains a broader Python composition lab, so this branch will not duplicate
that implementation.

The next admissible gate is a new design-only cross-implementation
reconciliation preregistration. It must compare raw root handling, `O_UNIQUE`,
ancestor and private-directory stability, APFS fingerprints, SQLite pathname
reopening, and ACL/clone/snapshot gaps before selecting any common reference
behavior. It must keep real inputs, trust provisioning, trusted time, replay
claims, capability minting, freeze authority, and G1.4 closed.
