# Engram G1 Authenticated Freeze-Authority Adapter Isolated Lab

Date: 2026-07-18

Status: **SYNTHETIC IMPLEMENTATION GATE EXERCISED / DEFAULT OFF / NO AUTHORITY**

## Decision

This lane implements the smallest offline laboratory needed to falsify the
security mechanics preregistered by the G1 authenticated freeze-authority
adapter contract. It is not the real adapter, does not accept real private
inputs or credentials, and is not G1.4.

The only positive laboratory verdict is
`SYNTHETIC_IMPLEMENTATION_GATE_EXERCISED_NO_AUTHORITY`. Production authority
and G1.4 states remain unrepresentable. The module is not imported by a crate,
MCP tool, daemon, migration, or runtime registry. Construction defaults to
`enabled=False`; the exact mode must be `SYNTHETIC_KAT` and every input must
carry explicit `synthetic_fixture=true` and `production_admissible=false`
markers.

The public contract and implementation identities are:

- contract SHA-256
  `f9b913c50eaf477c58a11bbf9526070c43137fe91098388d8260f84eb51a3b14`;
- implementation SHA-256
  `50e35469af07a81b6eef85fba5c83c92076efe1931b2ee932d8e2d05907ebc94`;
- adversarial checker SHA-256
  `e9aec0676148591e44181b36bf6f0a3ad62f130e1c92ed88bdd3cf7519b4c69e`;
- shell entry-point SHA-256
  `6f81855d87d348e1e096adad9df2b271385edea3eed52695532155bac06e4895`.

The gate pins preregistration commit
`632918db75f65030d3ac15bc991b51a9c938cba6` and hardened G1.3 commit
`7062869196d1a3ff8bb72572a39700e65130cde4`, including their exact public
contract, validator, and checker digests.

## What the lab proves

### Canonical bytes and signatures

The implementation rejects duplicate JSON keys, BOMs, non-UTF-8, unpaired
surrogates, floats, non-finite values, and integers outside the exact IEEE-754
safe range. For the remaining JSON domain it emits exact RFC 8785 bytes,
including UTF-16 property-name ordering. The checker fixes both an ordering KAT
and RFC 8032 Ed25519 test vector 1.

Five distinct public deterministic KAT keys sign one exact envelope under the
five preregistered role domains. The packet carries only role, key ID, epoch,
and detached signatures. It cannot carry a public key. The private ledger
selects each role/key/epoch and rechecks revocation inside the claim
transaction. Partial quorum, duplicate identity, injected key material, wrong
domain, changed signature, unknown epoch, and revoked key fail closed.

The same ledger contains a sixth, separately scoped public KAT key for a signed
time checkpoint. Synthetic seeds are public test vectors and are never trust
credentials.

### Retained-descriptor custody

The Darwin-only custody session resolves the configured repository root, Git
common directory, private directory, and every input component with
`openat`/`dir_fd`, `O_NOFOLLOW`, and retained descriptors. Private directories
must be euid-owned mode `0700`; files must be one euid-owned regular inode with
mode `0600` and `st_nlink == 1`.

Bytes are read and hashed from retained file descriptors. Before atomic claim,
the session repeats `fstat`, rereads bytes, and resolves each final name from
its retained parent descriptor. Device, inode, mode, owner, link count, size,
timestamps, and bytes must remain unchanged. The repository root, Git common
directory, every private parent, every private file, and the external ledger
must share one Darwin `fstatfs` identity. `MNT_LOCAL` is mandatory and known
network/FUSE filesystem types are rejected.

The checker creates only public synthetic data in temporary owner-only
directories, then removes those generated directories. It demonstrates
hardlink, symlink, unsafe mode, directory-mode, final-name swap, in-place byte
mutation, and remote-filesystem rejection.

### Packet-independent trust and one-use CAS

The trust/claim database is created outside the repository in an owner-only
directory. SQLite runs with `journal_mode=DELETE`, `synchronous=EXTRA`, foreign
keys, closed schema, disabled extensions, and `BEGIN IMMEDIATE` revision CAS.
Keys, revocations, claim events, and capability events are append-only.

Every open recomputes:

1. the exact SQLite schema digest;
2. the key-set-derived ledger identity;
3. the genesis hash;
4. every revocation, claim, and capability event hash in contiguous revision
   order;
5. the final chain head; and
6. the per-scope sequence and trusted-time high-water projection.

A separate process-private external revision-anchor double rejects an older
database snapshot even if that snapshot is internally consistent. Successful
claims and fail-closed denials both consume the exact envelope digest, nonce,
and per-scope sequence. Replays after either state are rejected. A denial that
does not complete trusted-time verification is chain-recorded and absorbing,
but cannot advance the trusted-time projection. Checker cases also rewrite a
key behind a restored trigger, alter a claim event, lower the time high-water
row, and remove a schema object; all are detected on the next open.

Transaction failure automatically attempts rollback. If rollback itself
fails, the ledger writes an owner-only, append-only, fsynced synthetic lesson
record and requires the caller to stop retrying and preserve evidence. The
record contains no packet, path, key, identity, or manifest material.

### Trusted time and non-bearer capability

Authority time is derived from a signed synthetic checkpoint plus a monotonic
sample and boot epoch, never from local wall clock alone. The envelope binds a
minimum 32-byte nonce, exact sequence, issue time, expiry, checkpoint bytes,
boot epoch, repository, and scope. Claim time is bounded to 15 minutes; the
ledger stores monotonic, trusted-UTC, checkpoint-sequence, and scope-sequence
high-water values in the authenticated event chain. Monotonic values are
ordered only inside one boot epoch. A changed epoch must carry an issued time
strictly above the prior trusted UTC and a strictly newer signed checkpoint;
only then may it replace the prior boot's monotonic domain. Checkpoint sequence
regression remains forbidden within one boot.

The returned capability is a nonserializable process-local object. It binds the
creator PID/process identity and an authorized Ed25519 consumer public key. Its
only method requires proof of possession and an atomic one-use ledger event.
The method merely exercises the binding for a future separate G1.4 design
review and emits
`SYNTHETIC_SUCCESSOR_BINDING_EXERCISED_G1_4_REMAINS_CLOSED`. It grants no data,
execution, mutation, write, or promotion authority.

## Human-audit policy

No human approval is required for this reversible synthetic KAT, ordinary
fail-closed denial, or unchanged rerun. No real trust root is provisioned, no
real key is rotated or revoked, and no production path is enabled, so this lane
does not exercise a manual safety-audit transition.

A separate manual safety audit remains mandatory before initial real trust-root
provisioning, real key rotation/revocation, role or quorum changes, repository,
scope, or predecessor widening, hardlink/mount/filesystem-policy changes, first
production enablement, or after suspected secret/privacy/identity exposure.

## Explicit limitations

This gate intentionally does not claim production readiness:

- public deterministic seeds and fixed time values are KAT material, not
  secrets or external time;
- the external revision anchor is process-private and synthetic, not a durable
  independent failure domain;
- SQLite is guarded by a retained sentinel and before/after inode checks, but
  the stock Darwin SQLite API still reopens by path rather than accepting the
  retained descriptor through a custom VFS; any post-commit path/inode drift
  therefore quarantines the process-private anchor instead of attempting an
  unsafe automatic recovery;
- repository-root and Git-common-dir identities plus exact public artifact
  hashes are retained, but the lab does not implement a descriptor-native Git
  object database parser;
- process binding includes boot epoch, PID, parent PID, euid, and implementation
  identity, but not an OS-attested process-start token;
- synthetic role packets prove exact byte/digest binding and quorum mechanics,
  not real G1.3 private-chain semantics;
- only Darwin/APFS-like local mounts are exercised; there is no Linux Landlock,
  macOS Seatbelt, HSM, keychain, remote KMS, real custodian, or network provider;
- no real candidate manifest, FIT, query, identity, or corpus material is read;
  and
- no G1.4 design, implementation, access, execution, retrieval mutation, live
  store write, or runtime promotion is opened.

Those gaps are reserved for separate threat-reviewed transitions. This
synthetic lane cannot be reinterpreted as their authorization.

## Run

```bash
scripts/check-engram-g1-authenticated-freeze-authority-adapter-isolated-lab.sh
```

The checker currently executes 259 assertions/mutation cases and ends only on
`PASS_SYNTHETIC_ISOLATED_LAB_NO_AUTHORITY` with `production_admissible=false`
and `g1_4_open=false`.
