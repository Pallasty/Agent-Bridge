# EnGram G1 synthetic retained-descriptor custody shadow

Date: 2026-07-18
State: `SYNTHETIC_RETAINED_DESCRIPTOR_SHADOW_IMPLEMENTED_NO_AUTHORITY`
Real adapter state: `PENDING_IMPLEMENTATION_PREREQUISITES`

## Decision

Implement the next prerequisite as a private, default-off macOS/APFS shadow in
`ab-store`. It may read only bytes placed in a disposable test tree by the same
test process. It proves that a bounded file can be reached, read, hashed, and
revalidated while every directory and file descriptor remains open.

This is not a real secure-custody capture. The only constructor for its entry
permit is compiled under `cfg(test)`, the module is not public, and it has no
bridge, MCP, database, environment, clock, network, process, or runtime path.
It does not call or import the preceding authenticated-envelope shadow.

## Ancestry

The frozen predecessor is the clean synthetic five-signature envelope commit:

- commit `2cca958844bc4ddf06954737775d40560119b8d1`;
- contract `066c77027635ef6f0ab388e9bee9cf094a597c7cc1a23cd867aa83d78d8bf6d7`;
- validator `57e0b30fb459c1ac3ec2d9a0eff9ee6673fbd704f2b94702d5a5ebc35df76fe0`;
- Rust module `5f3285482c27a73b768ca3c0726031184cb022516d9d48c4abe4258c4ed117ef`;
- checker `8f602104ad6e6b35af4fe4e681f02c8303f3cc98256d119a0216e58cde24e6d4`.

At implementation start, the successor branch merged the then-current GitLab
and GitHub `master` at `1f44c69d31ae29d0cd6c90e84294b3ad0407d9a0`. The conflict-free historical
merge anchor is `242573aad4595d307af2d9ffd59052ac2dd63a74`; both the predecessor and that
master snapshot remain ancestors.

During closeout, both remotes advanced together to
`5f509375248aae43b7524effd30f023c86d83087`. The branch merged that head at
`e92456c7f8d0e2c0365f3033d86cfad8beca4495`. The only textual conflicts were
parallel additions to the Cargo feature list and the evaluation README; both
were resolved additively. No custody implementation file conflicted. The new
master includes a separate Python authenticated-freeze adapter isolated lab at
`bdd0b07b5e9afcc20d030e7e3dcfd404d44e8d54`. That broader synthetic lab does
not supersede this narrower Rust descriptor-lifetime falsification surface and
does not grant either surface real authority.

The frozen contract intentionally retains the implementation-start ancestry
anchor and reviewed artifact bytes. It is a historical lower-bound receipt,
not a claim that `1f44c69d` remains the live remote head.

## Closed implementation surface

The feature is `engram-g1-secure-custody-shadow-synthetic`. It is absent from
the default feature list and only exposes a private module when the target is
macOS. On another operating system there is no callable module surface.

The accepted test tree has a deliberately narrow profile:

- the root path is absolute and its final name starts with
  `agent-bridge-engram-g1-custody-shadow-`;
- the synthetic root and all relative directories are owned by the effective
  uid with exact mode `0700`;
- the final object is an effective-uid-owned regular file with exact mode
  `0600`, `st_nlink == 1`, and at most 1 MiB;
- the relative path has 1–16 literal child components; a component is at most
  255 bytes and cannot be empty, `.`, `..`, contain `/`, or contain NUL;
- the absolute root is parsed from its raw OS bytes, so dot/dot-dot components,
  repeated separators, and a trailing separator are rejected rather than
  silently normalized;
- the synthetic root and every descendant must remain on one local APFS mount;
  unknown, network, and FUSE filesystems fail closed.

APFS-only is intentionally narrower than the future production question. Any
filesystem-policy widening is a separate manual transition audit, not a code
constant adjustment hidden inside this shadow.

Exact `0700`/`0600` proves only the POSIX mode-bit profile. This shadow does not
inspect Darwin extended ACL entries and does not prove the absence of APFS
clones, snapshots, or backup aliases. Those omissions are explicit reasons the
real secure-custody result remains false.

## Descriptor protocol

The shadow performs this sequence while retaining every opened descriptor:

1. Open `/` read-only with `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK`.
2. Parse the absolute synthetic root without canonicalization and open every
   component relative to its retained parent with `openat` and the same
   no-follow directory flags.
3. Open each relative directory component with the same procedure. Validate
   effective uid, exact `0700`, file type, device, and mount fingerprint.
4. From the retained final parent, call `fstatat(..., AT_SYMLINK_NOFOLLOW)` on
   the file name and require a bounded effective-uid-owned `0600` regular file
   with one link.
5. Open the file relative to that parent with
   `O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK|O_UNIQUE`; require Darwin to
   atomically reject a multi-link target and require its descriptor metadata to
   equal the pre-open name metadata.
6. Read no more than 1 MiB plus one detection byte from the retained file
   descriptor and compute SHA-256. No pathname is reopened to obtain bytes.
7. Re-run `fstat` on the file, compare all captured identity and mutation
   metadata except access time, and re-run `fstatfs`.
8. Re-run no-follow `fstatat` on the final name and require it to identify the
   retained file device, inode, type, and stable metadata.
9. For every retained directory, first revalidate its child name from the
   retained parent, then re-run descriptor metadata and mount checks. The
   synthetic root and relative private directories require the full snapshot
   (except atime) to remain stable; `/` and pre-root system ancestors require
   device, inode, and type identity. This catches a renamed or replaced
   repository root or parent even when the old descriptor still reads the
   original inode.
10. Compare the bytes against an independently supplied nonzero SHA-256 and
    exact length. Only then return synthetic conformance.

`O_NONBLOCK` prevents a raced FIFO or device substitution from hanging before
the post-open type check. `O_UNIQUE` is pinned to the current Darwin SDK value
because libc 0.2.186 does not yet export it; an unsupported kernel fails the
open closed. The implementation returns static error codes and messages; it
does not echo errno, paths, uid, inode, descriptor numbers, mount names, or
content.

## Stability and mount binding

The retained file snapshot binds device, inode, type/mode, link count, uid,
gid, rdev, size, block allocation, block size, modification time, change time,
birth time, flags, and generation. Access time is intentionally excluded
because a read may update it.

The mount fingerprint binds device, Darwin fsid bytes, filesystem type name and
number, flags, mounted-on name, and mounted-from name. The fingerprint must be
stable before and after capture, `MNT_LOCAL` must be set, and the type name must
be exactly `apfs`. Device equality is also enforced for the synthetic root,
all relative directories, and the file.

The descriptor-chain receipt is a domain-separated SHA-256 commitment over
synthetic descriptor identities plus the content digest. The private result
does not expose raw path, uid, inode, descriptor, mount, or content values.

## Deterministic attack evidence

Thirteen focused tests cover:

- successful retained traversal, hashing, and final revalidation;
- relative empty/dot/dot-dot/slash/NUL forms and absolute raw dot, repeated,
  trailing-separator, or relative-root forms;
- directory and root symlinks;
- wrong root, directory, and file modes;
- non-synthetic root names;
- file symlink, directory-as-file, FIFO, and oversized substitutions;
- a hard link present before open;
- a final-name swap after read;
- in-place content mutation after read;
- a hard link created after read;
- a retained parent renamed and replaced after read;
- the wrong independent content binding; and
- nonlocal/NFS/FUSE rejection versus the exact local APFS allowlist.

The after-read mutations use a test-only deterministic hook. The ordinary
entrypoint always supplies an empty hook, and neither entrypoint is callable
without the test-only permit.

## Current zero-authority result

A successful result may make only synthetic descriptor-conformance facts true:
component-by-component no-follow traversal, retained descriptor lifetime,
effective-uid ownership plus exact POSIX mode-bit checks, single-link
regular-file policy, local APFS identity, private-directory before/after
stability, system-ancestor object identity, final name-to-inode revalidation,
and independent synthetic byte binding.

The following remain unconditionally false:

- real secure-custody capture;
- composition with authenticated signatures;
- real repository, manifest membership, role, key, trust-root, or private
  corpus evidence;
- durable trust revision, trusted time, replay CAS, or claim-time revocation;
- capability minting, freeze authority, G1.4 readiness, write, execution,
  promotion, or runtime authority.

## Human-audit boundary

This default-off disposable test does not cross a real custody or authority
transition and needs no manual audit. A manual audit remains mandatory before
filesystem-policy widening, first real private-corpus access, initial trust-root
provisioning or rotation, signer/quorum/scope changes, first production
enablement, and any suspected secret, privacy, or identity exposure. A failed
reversible test is simply rejected; a rollback failure still requires durable
evidence and a lesson.

## Next admissible gate

The frozen contract's sole successor remains a separate design
preregistration for atomic synthetic composition of authenticated-envelope and
retained-descriptor custody conformance. It does not itself authorize that
implementation.

Because current master now contains an independently developed, broader Python
isolated lab that already composes synthetic signatures, custody, time, replay,
and a one-use capability, this branch must not open a duplicate composition
implementation. The next operationally admissible step is instead a separate
cross-implementation reconciliation preregistration. It must compare the two
custody protocols, including raw absolute-root parsing, `O_UNIQUE`, system
ancestor identity, private-directory stability, APFS fingerprinting, SQLite
path reopening, and their explicit ACL/clone/snapshot gaps, before selecting
any shared reference behavior.

That reconciliation must keep real private input, trust provisioning, trusted
time, replay claims, capability minting, freeze authority, and G1.4 closed. It
needs a new threat review specifically for check/use atomicity and for
preventing two individually synthetic successes from being laundered into real
authority. This closeout routing note does not mutate the reviewed frozen
contract or retroactively authorize the landed independent lab.

## Frozen public artifacts

- contract: `782fafff5b456d2ddd5fbe95d833525a1e62e4d5416ddf481d9ba3e36e582a84`;
- validator: `25badec3b0ca55f2a07f8038177a33306a56345fe670bff5c4784b586a3b3e5a`;
- Rust module: `ef516c9e8784eac869de38aa11c217de1602f7a9d47719216b620b6401356b82`;
- checker: `331736d1244584c25cff50e1c77d93c38668bf9a93543c7ce14602326b699138`.

Run:

```bash
scripts/check-engram-g1-secure-custody-retained-descriptor-shadow.sh
```

The checker pins the public bytes, recursively mutates every contract leaf,
rejects duplicate/symlinked/byte-drifted contracts, checks private/default-off
and test-permit wiring, runs all 13 Rust attacks, verifies both required Git
ancestors, builds with the feature absent, and then runs the complete preceding
authenticated-envelope checker chain.
