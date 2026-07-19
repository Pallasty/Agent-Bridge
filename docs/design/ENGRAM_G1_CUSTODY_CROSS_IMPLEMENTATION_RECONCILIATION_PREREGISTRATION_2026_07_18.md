# Engram G1 custody cross-implementation reconciliation preregistration

Date: 2026-07-18

State: `SOURCE_PINNED_MATRIX_VALIDATED_NO_AUTHORITY`

## Decision

Freeze a design-only comparison between the standalone Rust retained-descriptor
custody shadow and the broader Python authenticated-freeze adapter isolated
lab. The two sources are not implementations of one interchangeable custody
contract. No exact-equivalence row is registered, and neither the union nor an
automatic intersection of their controls may be promoted into a stronger
claim.

This gate adds no differential harness and modifies neither source
implementation. It reads only checked-in public artifacts. It does not open a
private path, ledger, trust root, runtime, MCP surface, or G1.4 successor.

## Frozen sources

The Rust source is fixed at commit
`db27075ff3eb473b5ca779b57bd86094290dc1c6`:

- module SHA-256
  `ef516c9e8784eac869de38aa11c217de1602f7a9d47719216b620b6401356b82`;
- contract SHA-256
  `782fafff5b456d2ddd5fbe95d833525a1e62e4d5416ddf481d9ba3e36e582a84`;
- validator SHA-256
  `25badec3b0ca55f2a07f8038177a33306a56345fe670bff5c4784b586a3b3e5a`;
- checker SHA-256
  `331736d1244584c25cff50e1c77d93c38668bf9a93543c7ce14602326b699138`.

The Python source is fixed at commit
`bdd0b07b5e9afcc20d030e7e3dcfd404d44e8d54`:

- implementation SHA-256
  `50e35469af07a81b6eef85fba5c83c92076efe1931b2ee932d8e2d05907ebc94`;
- contract SHA-256
  `f9b913c50eaf477c58a11bbf9526070c43137fe91098388d8260f84eb51a3b14`;
- checker SHA-256
  `e9aec0676148591e44181b36bf6f0a3ad62f130e1c92ed88bdd3cf7519b4c69e`;
- shell entrypoint SHA-256
  `6f81855d87d348e1e096adad9df2b271385edea3eed52695532155bac06e4895`.

Both GitLab and GitHub master were synchronized at
`33c2c4df78ef302fd0538986b95fa40a3711ba86` before preregistration. The isolated
branch merged that head at `9e441542f5bf424b4b07ac105ccc1d25c1676d81`.
The intervening master work is BioCortex S20B/T07 and does not alter either
frozen custody source.

## Classification discipline

Every one of the 28 comparison rows uses one of six registered labels:

- `SHARED_INTENT_DIFFERENT_MECHANISM`;
- `RUST_STRICTER`;
- `PYTHON_BROADER_SCOPE`;
- `PYTHON_ONLY_COMPOSITION_CONTROL`;
- `NONCOMPARABLE`; or
- `SHARED_GAP`.

There is intentionally no `EQUIVALENT` label. Two accepts do not prove the same
security semantics, and two rejects do not prove the same failure cause. A
one-sided rejection may reflect stricter mechanics, different scope, or a
composition-only prerequisite; the receipt must retain that distinction.

## Main findings

### Rust-specific strictness

The Rust shadow is narrower but stronger at the descriptor and Darwin
filesystem boundary:

- it parses absolute paths from raw OS bytes and rejects repeated separators,
  dot components, trailing separators, NUL, excessive depth, and long
  components before normalization;
- it retains `/` and every absolute ancestor, then re-resolves each child name
  from its retained parent;
- directory opens include `O_NONBLOCK`; file opens additionally include
  `O_NONBLOCK` and Darwin `O_UNIQUE`;
- it binds a larger Darwin stat snapshot, including gid, rdev, allocation,
  birth time, flags, and generation;
- it revalidates private-directory metadata and directory-name chains, not only
  private file names; and
- it accepts only exact local APFS and binds filesystem number, full flags,
  mount-on, and mount-from data in addition to device and fsid.

Those properties cannot be projected into the Python result merely because the
Python lab also uses no-follow file descriptors.

### Python-specific breadth

The Python isolated lab covers a larger synthetic composition:

- a fixed multi-file manifest, role-packet, checkpoint, signature, and envelope
  set rather than one file;
- repository-root and Git-common-directory identities;
- registered public artifact hashes;
- an external owner-only SQLite trust and claim ledger double;
- signed checkpoint and monotonic trusted-time mechanics;
- absorbing replay claims and revision CAS; and
- a process/key-bound, nonserializable, one-use synthetic capability.

Those composition controls cannot be projected into the Rust result. The Rust
shadow explicitly has no trust, time, replay, capability, or transaction
surface.

### Python custody gaps relative to Rust

The Python path walker uses `Path.parts`, after pathlib normalization, and
closes intermediate absolute ancestors while descending. Its file opens omit
`O_NONBLOCK` and `O_UNIQUE`. Its claim-time directory loop rechecks mount
identity but not private-directory metadata or names from retained parents.
Its reduced file tuple omits several Darwin stat fields captured by Rust.

These are registered differences, not vulnerabilities adjudicated by this
design-only gate. Eighteen future probes specify how to observe them without
granting authority.

### Shared unresolved gaps

Neither implementation proves absence of Darwin extended ACL entries. Neither
proves absence of APFS clones, snapshots, or backup aliases. Exact POSIX modes
and `st_nlink == 1` therefore remain narrower than exclusive custody.

Both implementations also lack a proved atomic filesystem-and-ledger
linearization point. The Rust shadow has no ledger. The Python lab calls
filesystem revalidation from inside `BEGIN IMMEDIATE`, then appends the event
and commits, but it does not rerun custody after commit.

## SQLite pathname reopening boundary

The Python ledger retains a no-follow sentinel descriptor and compares its
inode before and after the operation. Stock SQLite is nevertheless opened by
the absolute pathname through `sqlite3.connect(path.as_uri())`; it is not
opened through the retained descriptor or a reviewed descriptor-native VFS.

That design deliberately quarantines detected drift, but it does not make the
SQLite target and sentinel one atomic object at open time. The preregistered
future probe must attempt a swap between sentinel open and SQLite pathname
open, recording sentinel inode, SQLite target identity where observable, and
the fail-closed outcome. This gate selects no VFS or recovery strategy.

## Linearization model

The frozen event vocabulary is:

1. `F0_DESCRIPTOR_OPEN`;
2. `F1_INITIAL_BYTE_READ`;
3. `L0_BEGIN_IMMEDIATE`;
4. `F2_PRECOMMIT_CUSTODY_REVALIDATION`;
5. `L1_EVENT_APPEND_AND_CAS`;
6. `L2_COMMIT`; and
7. `F3_POSTCOMMIT_CUSTODY_REVALIDATION`.

Rust currently exercises `F0`, `F1`, and `F2` without a ledger. Python
exercises `F0`, `F1`, `L0`, `F2`, `L1`, and `L2`; it does not exercise `F3`.
The preregistration therefore keeps all cross-domain atomicity fields false.
Mutation after `F2` and before `L2`, plus mutation after `L2`, are mandatory
future attacks.

## Required future evidence

The contract fixes 18 disposable synthetic probes spanning:

- raw path spelling and bounded-component grammar;
- absolute-ancestor and private-parent replacement;
- private-directory metadata drift;
- persistent and raced hard links;
- FIFO or device substitution with a bounded child-process timeout;
- file rebinding and in-place byte mutation;
- unknown local filesystem and mount-fingerprint drift;
- extended Darwin metadata drift;
- public artifact name rebinding;
- SQLite pathname reopen swapping;
- precommit-to-commit and postcommit mutation; and
- explicit ACL and APFS copy-alias unresolved-gap cases.

Every probe records per-implementation outcomes and exact observation epochs.
Every probe has `authority_if_pass=false`. ACL and copy-alias cases must emit
`UNRESOLVED_SHARED_GAP` unless a separately reviewed control exists.

## Adjudication rules

- Source hash drift rejects the entire comparison.
- Contract drift rejects before semantic interpretation.
- No row may be upgraded by selecting the strongest property from each source.
- A Python transaction cannot authenticate the standalone Rust custody result.
- A Rust path or mount control cannot authenticate Python ledger composition.
- A future differential harness may report observations only; it cannot select
  production policy or represent equivalence.
- No comparison outcome may flip a real custody, freeze, G1.4, or runtime field
  to true.

## Human-audit boundary

Routine validation of this public contract and unchanged predecessor checkers
needs no manual audit. A manual transition audit remains mandatory before real
private input, real trust-root provisioning, filesystem-policy widening,
descriptor or SQLite VFS strategy changes, first production enablement, or
suspected secret, privacy, or identity exposure.

## Frozen preregistration artifacts

- contract SHA-256
  `d0ea62745ff239c988e5725240e0a0e44796cbce5c1b5e5a4dc499c7afa84fbc`;
- validator SHA-256
  `1ec29777abe0d6ed5624f654aad5c685196f1a30b451241470714319c5c78c38`;
- checker SHA-256
  `a8bef61838c664c48ec7db84c4025cb222084a2003d31da4eec9cb1ac66d9cbb`.

The checker hash is an external Git/review identity; the executable pins the
contract, validator, and both complete predecessor source sets without trying
to self-pin circularly.

Run:

```bash
scripts/check-engram-g1-custody-cross-implementation-reconciliation.sh
```

The checker recursively mutates at least 375 registered leaves, rejects list,
schema, byte, duplicate-field, and symlink drift, verifies static source
witnesses for the matrix, proves there is no crate/runtime surface, and runs
both full predecessor checker chains: Rust custody plus its ten-signature
predecessor tests, and the Python 259-check isolated lab.

## Next gate

Only a separate synthetic differential-harness implementation may follow, and
only after an independent threat review of this matrix and linearization model.
That harness must use disposable public synthetic fixtures, keep both source
profiles separately named, and preserve a zero-authority result. It may not
load real private inputs, widen the filesystem allowlist, add a runtime
entrypoint, or open G1.4.
